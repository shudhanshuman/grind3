# Chess Engine — Theory From Zero

> Current state (`~/chess_eng`): 8×8 list-of-strings board in `ChessEngine.py` (`GameState`) + PyGame rendering in `ChessMain.py`. Your README says "AlphaZero-style engine that can beat me".
>
> Recommended path: **keep the PyGame UI**, write the engine as a separate **C++ program that speaks UCI**. The UI talks to it through a subprocess (and so can any chess GUI or lichess-bot). Classical alpha-beta first → then **NNUE** (a neural eval, the modern Stockfish approach) → then optionally an **AlphaZero-style MCTS + policy/value net** as a second engine you can pit against the first. A pure-Python engine tops out around ~1500–1800 Elo because it's 50–100× slower. C++ makes every later idea pay off.

---

## 1. Chess rules that bite programmers

You know how pieces move. These are the edge cases that break move generators:
- **Castling** (O-O / O-O-O): king and rook haven't moved (track 4 **castling-rights** flags), the squares between are empty, **the king is not in check, doesn't pass through an attacked square, and doesn't land on one**. The rook may pass through an attacked square (queenside b1/b8).
- **En passant:** only immediately after an enemy pawn's double push. Track the **en-passant target square**. Nasty edge case: the en-passant capture can expose your king along the **rank** (both pawns vanish from the same rank). Test position for this in §3.
- **Promotion:** to Q, R, B or N (underpromotion matters, e.g. knight promotion with check). Promotion with capture.
- **Legality:** a move is illegal if it leaves your own king in check. This includes moving a **pinned** piece and the king walking into an attacked square, including a square "behind" itself along a slider's line.
- **Game end:** checkmate, stalemate (no legal moves, not in check = draw), **50-move rule** (halfmove clock, reset on pawn move/capture), **threefold repetition** (needs position hashing), insufficient material.

### FEN (Forsyth–Edwards Notation): learn to read and write it
`rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1`
= piece placement (rank 8 → 1) · side to move · castling rights · en-passant square · halfmove clock · fullmove number. **Your first engine function is `load_fen` / `to_fen`.** All tests are FEN positions.

Notation: squares a1..h8. In code, index 0..63 with **a1 = 0, h1 = 7, a8 = 56, h8 = 63** (the "little-endian rank-file" mapping most engines use).

---

## 2. Board representation

| Representation | Idea | Verdict |
|---|---|---|
| 8×8 array (what you have) | `board[r][c]` | Easy, slow, needs bounds checks |
| **10×12 mailbox / 0x88** | Padded board, so off-board moves land on sentinel squares (0x88: `sq & 0x88` != 0 means off-board) | Good stepping stone |
| **Bitboards** | One 64-bit integer per (color, piece type): 12 bitboards. Bit i set = piece on square i. | **What all strong engines use. Go here.** |

### Bitboard toolkit
- Set ops: `occupied = white | black`, `empty = ~occupied`, `us & them`, etc.
- Shifts: north = `<< 8`, south = `>> 8`, east = `<< 1` masked with `~FILE_A` (to avoid wrap-around), west = `>> 1` & `~FILE_H`.
- Pawn pushes for all pawns at once: `single = (pawns << 8) & empty`, `double = ((single & RANK_3) << 8) & empty`.
- **Iterate pieces:** `while (bb) { sq = ctz(bb); bb &= bb - 1; }` (`__builtin_ctzll` / `std::countr_zero`, which pops the lowest set bit).
- `popcount` for counting (material, mobility).
- **Leapers** (knight, king, pawn attacks): precomputed lookup tables `KNIGHT_ATTACKS[64]`.
- **Sliders** (bishop, rook, queen) depend on blockers:
  - Simple: loop ray by ray until you hit a piece ("classical approach" with ray tables + `ctz/clz` of blockers).
  - Fast: **Magic bitboards**. `attacks = TABLE[sq][((occupied & mask[sq]) * MAGIC[sq]) >> shift[sq]]`. A perfect-hash multiplication trick. Use known magic numbers (find your own with a random search later). On x86, **PEXT** (BMI2) does the same without magics. Your M2 has no PEXT, so use magics.

### Move encoding
16-bit move: from (6 bits) | to (6 bits) | flags (4 bits: quiet, double push, castle K/Q, capture, en-passant, 4 promotions × capture/non-capture). Compact, fast to copy.

### Make / unmake
- `make_move` updates the bitboards, a mailbox `piece_on[64]` (keep both, since mailbox answers "what's on e4?" fast), castling rights, the ep square, clocks and the **Zobrist hash**. `unmake_move` restores. Or use **copy-make** (copy the whole ~200-byte state per ply), which is simpler, less bug-prone, and fast enough.

---

## 3. Move generation and PERFT (the hardest 50%)

**Pseudo-legal** generation (ignore self-check) + a legality check after making the move ("is my king attacked?") is the simplest correct approach. **Fully legal** generation (compute pins and check masks up front) is faster. Do pseudo-legal first.

`is_square_attacked(sq, by_color)`: the "super-piece" trick. From `sq`, generate knight attacks and see if they hit enemy knights, bishop attacks for enemy bishops/queens, rook attacks for rooks/queens, pawn attacks, king attacks.

### PERFT: your correctness test harness
`perft(depth)` = number of leaf nodes of the legal move tree. Compare with known values. **If any number is off, you have a bug.** Use **"divide"** (perft per root move) and compare against Stockfish's `go perft N` or python-chess to binary-search the bug.

| Position | d1 | d2 | d3 | d4 | d5 | d6 |
|---|---|---|---|---|---|---|
| Start pos | 20 | 400 | 8,902 | 197,281 | 4,865,609 | 119,060,324 |
| **Kiwipete** `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1` | 48 | 2,039 | 97,862 | 4,085,603 | 193,690,690 | |

Chess Programming Wiki's "Perft Results" page lists positions 3–6, which cover en-passant pins, promotions and castling-through-check. **Pass them all before writing any search.** Engines that skip this spend weeks chasing phantom search bugs that were actually move-gen bugs.

---

## 4. Search

### Minimax → Negamax
- Game tree: positions are nodes, moves are edges. Minimax: max player picks the max child, min player picks the min.
- **Negamax:** `score(pos) = max over moves of −score(child)`. One function for both sides. Eval is always from the side-to-move's perspective.
- Branching factor in chess ≈ 35. Depth d costs 35^d nodes, so depth 6 ≈ 1.8 billion. Too many.

### Alpha-beta pruning
- Keep a window [α, β]: α = the best score we're guaranteed, β = the best the opponent allows. If a move scores ≥ β, the opponent would never let us get here, so **cut off** (fail-high).
- With **perfect move ordering**, nodes ≈ 35^(d/2). You search twice as deep for the same cost. **So move ordering is everything.**

```
int negamax(pos, depth, alpha, beta):
    if depth == 0: return quiescence(pos, alpha, beta)
    for move in ordered_moves(pos):
        make(move)
        score = -negamax(pos, depth-1, -beta, -alpha)
        unmake(move)
        if score >= beta: return beta          // fail-hard cutoff
        alpha = max(alpha, score)
    if no legal moves: return in_check ? -MATE + ply : 0
    return alpha
```

### Essential additions, in the order to add them (measure Elo after each, see §7)
1. **Quiescence search:** at depth 0, keep searching **captures only** (plus promotions) until the position is quiet. "Stand pat" = static eval as a lower bound. Fixes the **horizon effect** (e.g. QxP looks great at depth 0 because the recapture is past the horizon). The single biggest strength gain.
2. **Move ordering:** TT/hash move first → captures by **MVV-LVA** (Most Valuable Victim – Least Valuable Attacker: PxQ before QxP) or SEE (static exchange evaluation) → **killer moves** (quiet moves that caused cutoffs at the same ply) → **history heuristic** (quiet moves that caused cutoffs anywhere, weighted by depth²).
3. **Iterative deepening:** search depth 1, 2, 3… until time runs out. It sounds wasteful but is *faster* overall because each iteration seeds move ordering (PV move, TT) for the next. It also gives you a move at any time → time management.
4. **Zobrist hashing:** random 64-bit number per (piece, square), side to move, castling right and ep file. Position hash = XOR of the present ones. Updated incrementally in make/unmake (XOR in/out). Used for the TT and repetition detection.
5. **Transposition table (TT):** a hash table keyed by Zobrist that stores {hash, depth, score, **bound type**, best move}. Bound type: **EXACT** (α < score < β), **LOWER** (fail-high, score ≥ β), **UPPER** (fail-low, score ≤ α). Lookup can cut off immediately or give the best move for ordering. Replacement scheme: depth-preferred + always-replace bucket. Mate scores need ply adjustment when stored/loaded.
6. **Principal Variation Search (PVS):** search the first move with the full window, the rest with a **null window** (α, α+1) to just prove they're worse. Re-search if one surprises.
7. **Null-move pruning:** "if I pass and I'm *still* ≥ β at reduced depth (R = 2–3), this position is so good I can cut." Don't use it in check or in pawn endgames (**zugzwang**).
8. **Late Move Reductions (LMR):** moves late in the ordering are probably bad, so search them at reduced depth and re-search at full depth only if they beat α. Huge depth gain.
9. **Aspiration windows:** at the root, search a narrow window around the last iteration's score. Re-search wider on failure.
10. Later: check extensions, futility pruning, reverse futility (static null move), late move pruning, SEE pruning in qsearch, singular extensions. One at a time, each tested.

**Repetition & 50-move** detection in search: keep a stack of hashes. Treat the first repetition inside the search as a draw.

### Time management
Simple: `time_for_move = remaining/30 + increment/2`. Stop iterative deepening when the next iteration likely won't finish. Check the clock every ~2048 nodes.

---

## 5. Evaluation

### Classical (hand-crafted, "HCE")
- **Material:** P=100, N=320, B=330, R=500, Q=900 (centipawns).
- **Piece-square tables (PST):** bonus/penalty per piece per square (knights in the centre good, on the rim bad, etc.).
- **Tapered eval:** separate middlegame and endgame tables, blended by a **game phase** derived from remaining non-pawn material. The king hides in the middlegame and centralizes in the endgame.
- **PeSTO tables:** published tuned midgame/endgame PSTs (CPW "PeSTO's Evaluation Function"). Material + PeSTO tapered PST alone ≈ a surprisingly strong engine (~2000+ with decent search).
- More terms: mobility, pawn structure (doubled/isolated/**passed pawns**), bishop pair, rooks on open files, king safety (pawn shield, attackers near king).
- **Texel tuning:** fit all eval weights by minimizing the MSE between `sigmoid(eval)` and actual game results over millions of positions. **This is logistic regression / gradient descent**, so it's your ML skillset.

### NNUE (Efficiently Updatable Neural Network): modern eval, your sweet spot
- Input: sparse one-hot features. Simplest form is **768 inputs** = 2 colours × 6 pieces × 64 squares (Stockfish uses king-relative "HalfKA"-style features).
- Architecture (simple, effective): `768 → 256 (accumulator, per perspective) → concat 512 → 1`, **clipped ReLU / SCReLU** activation.
- **The trick:** the first layer is huge but inputs change by only 2–4 features per move, so you **incrementally update** the accumulator: add/subtract weight columns on make/unmake instead of a full matmul. That's what makes the "EU" in NNUE.
- **Quantized int16/int8 inference** with SIMD. Same skills as your neural accelerator project.
- Training data: generate positions by self-play with your own engine (eval targets = search scores + game results), then train in PyTorch (or **bullet**, the Rust NNUE trainer most hobby engines use). A first net typically gains hundreds of Elo over HCE.

### AlphaZero-style (MCTS + policy/value net): what your README dreams of
- **MCTS** with **PUCT** selection: pick the child maximizing `Q(s,a) + c·P(s,a)·√N(s)/(1+N(s,a))`. Expand a leaf → the neural net gives **policy P** (move priors) and **value v** (expected outcome) → back up v. No alpha-beta and no handcrafted eval.
- Training loop: self-play with MCTS → (position, MCTS visit distribution, game result) → train the net (cross-entropy on policy + MSE on value) → repeat.
- Reality check: AlphaZero used thousands of TPUs. **Leela Chess Zero** took years of distributed community compute. On an M2 in a month, pure self-play from zero won't get strong.
- Feasible version: **supervised** pretraining on Lichess games / Stockfish-labelled positions (a small ResNet or transformer, policy + value heads), then MCTS on top. It can reach a level that beats casual humans (≈ you!), and it's a fantastic ML project. Treat it as **phase 2 / next semester**, after the alpha-beta engine works.
- Interview gold: *why did NNUE + alpha-beta (Stockfish) end up beating the pure AlphaZero approach in CPU-limited settings?* (Search depth × a cheap, accurate eval beats few nodes × an expensive eval when hardware is a CPU.)

---

## 6. UCI protocol (how engines talk)

Text over stdin/stdout:
```
GUI → uci                     Engine → id name MyEngine / uciok
GUI → isready                 Engine → readyok
GUI → position startpos moves e2e4 e7e5
GUI → go wtime 60000 btime 60000 winc 1000 binc 1000
Engine → info depth 8 score cp 34 nodes 120000 nps 900000 pv g1f3 b8c6
Engine → bestmove g1f3
```
Once UCI works: plug into **Cute Chess / En Croissant / Arena** GUIs, play vs other engines, deploy to Lichess with **lichess-bot**, and have your PyGame UI call it as a subprocess.

---

## 7. Testing strength properly

- **Never trust "it feels stronger."** Engine devs run **SPRT** (sequential probability ratio test): play thousands of fast games (e.g. 10s+0.1s) new-vs-old using **fastchess** or **cutechess-cli** with an opening book. Accept a patch only if it's statistically better.
- Elo from a match score: `ΔElo = −400·log10(1/score − 1)`.
- Sanity suites: WAC (Win At Chess) tactical positions, mate-in-N puzzles.
- Benchmarks: nodes per second (nps), time to depth, perft speed.

---

## 8. Build plan (suggested)
1. C++ bitboard board + FEN + move gen → **perft passes all CPW positions** (expect 3–5 days).
2. Negamax + alpha-beta + material/PST eval + qsearch + MVV-LVA → UCI → it plays! (~2 days)
3. Iterative deepening + TT + killers/history + PVS + null move + LMR + time management. SPRT each one.
4. PeSTO tapered eval → Texel tuning (optional).
5. NNUE: datagen → train in PyTorch → int16 incremental inference. (The ML-flavoured milestone.)
6. Hook into your PyGame UI + lichess-bot. Report rating on Lichess (bot account) / CCRL-style gauntlet results.
7. Phase 2 (later): MCTS + policy/value net version.

---

## 9. Interview questions
1. Explain minimax and alpha-beta. Best-case node count? Why does move ordering matter?
2. What's the horizon effect and how does quiescence search fix it?
3. What's a transposition table? Why store bound types? What's a hash collision's impact?
4. Zobrist hashing: why XOR? How is it updated incrementally?
5. Bitboards: generate all white pawn single pushes in one line. How do magic bitboards work?
6. Iterative deepening seems wasteful. Why is it actually faster?
7. Null-move pruning: why does zugzwang break it?
8. MCTS vs alpha-beta: when is each better? Explain PUCT and exploration vs exploitation.
9. How does NNUE stay fast despite a big first layer?
10. (General DSA link) Alpha-beta ≈ branch-and-bound. Game trees ≈ DFS with pruning. Zobrist ≈ hashing. TT ≈ cache/memoization. Interviewers like it when you connect these.

**AI-era probes:** "How did you know your move generator was correct?" (perft + divide vs Stockfish). "How do you know feature X helped?" (SPRT, with N games and the Elo ± error). "What did the NN learn? Did you try ablations?"

---

## 10. Resources (priority order)

**Videos (start here for intuition)**
1. **Sebastian Lague, "Coding Adventure: Chess"** and **"Coding Adventure: Making a Better Chess Bot"** (YouTube). The most beginner-friendly overview of the whole pipeline (board, move gen, search, eval, bugs he hit). Watch both on day 1, ~1.5 h total.
2. **Bluefever Software, "Programming a Chess Engine in C" (VICE series, YouTube, ~80 short videos)**. Old but complete, a step-by-step 10×12 mailbox engine. Use it as a reference for TT/search/UCI videos.
3. **Code Monkey King, "Bitboard CHESS ENGINE in C" (BBC series, YouTube)**. Bitboards + magic bitboards explained line by line. Watch the magic-bitboard episodes when you get there.

**Written (reference)**
4. **Chess Programming Wiki (chessprogramming.org)**. The bible. Read these pages: *Getting Started*, *Bitboards*, *General Setwise Operations*, *Magic Bitboards*, *Perft*, *Perft Results*, *Zobrist Hashing*, *Negamax*, *Alpha-Beta*, *Quiescence Search*, *MVV-LVA*, *Killer Heuristic*, *History Heuristic*, *Iterative Deepening*, *Transposition Table*, *Principal Variation Search*, *Null Move Pruning*, *Late Move Reductions*, *PeSTO's Evaluation Function*, *Tapered Eval*, *Texel's Tuning Method*, *NNUE*, *UCI*. It's dense: read the page when you're about to implement that feature, not all upfront.
5. **Rustic chess engine book (rustic-chess.org)**. A well-written book-style walkthrough of building an engine (board, move gen, search, testing). Excellent even if you write C++.
6. **Lichess blog by likeawizard, "How to build a chess engine" series**. A beginner's guide plus posts on bitboards and search trees.
7. **official-stockfish/nnue-pytorch, `docs/nnue.md` (GitHub)**. The definitive NNUE explainer (feature sets, accumulators, quantization). Read when you reach NNUE.
8. **AlphaZero paper: Silver et al., "A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play" (Science 2018)** + the **Leela Chess Zero docs/blog** for the practical version.

**Tools**
- **python-chess**: generate test positions, perft-divide against it, run quick matches.
- **Stockfish** (`go perft N`) for the divide comparisons.
- **fastchess / cutechess-cli** for SPRT. **lichess-bot** for deployment.
- Community: r/chessprogramming, **Engine Programming Discord / Stockfish Discord** (the most active place for help).

---

## 11. Metrics / resume line
> "C++ chess engine: magic bitboards (perft-verified on all CPW suites, X M nps), PVS alpha-beta with TT/null-move/LMR, NNUE evaluation trained on Y M self-generated positions in PyTorch with incremental int16 inference (+Z Elo over HCE, SPRT-verified). ~N Elo on Lichess as a bot."
