# Codeforces 1330 → 1600+ and Interview DSA — Theory & Plan

> Two related but different goals:
> 1. **Codeforces rating** (contest skill: speed, observations, math, constructive thinking).
> 2. **Placement/internship DSA** (OA + interview: standard patterns, clean code, explaining your approach, LeetCode-style).
>
> At 1330 (Pupil), the honest bottleneck is usually **solving Div2 B/C quickly and reliably**, not knowing advanced algorithms. Target for this month: **consistent 1500–1600 performance** (Specialist). Realistic if you do ~1.5–2 h/day plus every contest you can.

---

## 1. What separates 1300 from 1600

| At ~1300 | At ~1600 |
|---|---|
| Solves A, B sometimes slowly, C rarely | A+B in ~20–25 min, C regularly, sometimes D |
| Codes the first idea | Proves/greedy-checks the idea on small cases first |
| WA → stares at code | WA → writes a brute force + random tests (stress testing) |
| Knows algorithms by name | Recognizes *which* trick a problem wants (binary search on answer, prefix sums, parity, sorting + greedy) |
| Gets stuck on math | Comfortable with gcd/mod/parity/basic combinatorics |

Most Div2 B/C problems at 1200–1600 are **observation + greedy/constructive + simple math**, not heavy data structures.

---

## 2. Topic list (in order of ROI for 1300 → 1600)

**Tier 1: must be automatic**
1. **Sorting + greedy** (exchange argument: "why is swapping two adjacent choices never better?")
2. **Prefix sums** (1D, 2D, difference arrays for range updates), prefix XOR
3. **Two pointers / sliding window**
4. **Binary search**, especially **binary search on the answer** (monotonic predicate: "can we achieve ≥ x?")
5. **Math basics:** parity arguments, gcd/lcm, divisors in O(√n), **sieve**, prime factorization, **modular arithmetic** (mod 1e9+7, binary exponentiation, modular inverse via Fermat), nCr with precomputed factorials
6. **Constructive problems** ("output any array such that…"): try small n by hand, look for a pattern
7. **Bit manipulation:** XOR properties, checking bits, subsets via bitmask, `__builtin_popcount`
8. **Strings basics:** frequency counts, palindromes, two-pointer on strings
9. STL fluency in C++: `sort` with lambdas, `map`/`set` + `lower_bound`, `priority_queue`, `multiset`, `pair`/`tuple`

**Tier 2: needed for C/D at 1400–1700**
10. **Graphs:** BFS (shortest path unweighted, multi-source), DFS (components, cycle detection), **0-1 BFS**, **Dijkstra**, topological sort, bipartite check
11. **Trees:** DFS on trees, subtree sizes, depth, tree diameter (two BFS), rerooting (intro)
12. **DSU (disjoint set union)** with path compression + union by size
13. **DP basics:** 1D/2D DP, knapsack, LIS (O(n log n)), grid paths, DP on subsequences, simple bitmask DP, **DP state design** (the real skill)
14. **Stacks/monotonic stack** (next greater element), **deques** (sliding-window max)
15. Hashing / `map` tricks (count pairs with property, frequency of differences `a[i] - i`)
16. Interactive problems (binary search with queries). They appear in Div2 B/C.

**Tier 3: for 1700+ / next semester**
Segment tree (+ lazy), Fenwick tree, LCA (binary lifting), sparse tables, string hashing / KMP / Z-function, combinatorics & inclusion-exclusion, game theory (Grundy), digit DP, MST (Kruskal/Prim), shortest paths (Bellman-Ford, Floyd-Warshall).

### Interview-DSA topics that CF under-practices (add these)
- **Linked lists** (reverse, cycle detection with Floyd, merge, LRU cache = hashmap + doubly linked list)
- **Trees as objects** (BST validation, traversals iterative, LCA in a BST, serialize/deserialize)
- **Heaps** (top-k, merge k sorted lists, median of a stream with two heaps)
- **Tries** (prefix search, max XOR pair)
- **Backtracking** (subsets, permutations, N-queens, word search)
- **Intervals** (merge, meeting rooms)
- **Design problems** (LRU/LFU cache, rate limiter, iterator design)
- **Complexity analysis out loud**, plus clean, readable code (variable names matter in interviews, not in contests)

---

## 3. The daily routine (≈ 1.5–2 h, every day of the break)

| Block | Time | What |
|---|---|---|
| Warm-up | 15 min | 1 problem at **~1200** (speed + accuracy, solve in < 15 min) |
| Main | 60–75 min | **2 problems at 1400–1600**. ~30–40 min honest attempt each. Stuck → read the **hint/editorial, then close it and code it yourself**. |
| Upsolve / review | 15–20 min | Write a 2–3 line note per problem: *the key observation* + the pattern tag. (This "observation log" is the most underrated habit.) |

Weekly:
- **Every Codeforces round you can** (Div2/Div3/Div4, Educational). If a round clashes, do a **virtual contest** of an older round under timed conditions. **2–3 contests/virtuals per week.**
- After each contest: **upsolve the first problem you couldn't solve.** That problem is your exact growth edge.
- **AtCoder Beginner Contest (ABC)** on Saturdays: excellent, clean problems for C–E at your level.
- **1–2 interview-style problems/day** in the last week before the semester (Striver/NeetCode, see resources).

Rules of thumb (from the CF community):
- Practice at **your rating +100 to +300** (so 1400–1600 now). Mostly-1000 problems feel productive but don't move the rating.
- Look at the editorial after **20–30 min of being genuinely stuck** (Errichto's advice), not 2 hours and not 2 minutes.
- **Use the problemset filter by rating + tag**, but solve some **untagged** problems too (in contests nobody tells you the tag).
- Track performance per contest, not just rating: if you get 1600 *performance* consistently, the rating follows.

### Stress testing (learn this in week 1, it saves contests)
Write `brute.cpp` (obviously correct, slow), `gen.py` (random small input) and a shell loop that compares outputs until they differ. Then debug on the tiny failing input. This is also exactly how you'll verify your order book, chess engine and RTL (golden-model testing).

### Contest-day template
- Read A, B (and C) fully before coding. Check constraints → target complexity (n ≤ 2e5 means O(n log n); n ≤ 5000 means O(n²); n ≤ 20 means 2ⁿ).
- Edge cases: n = 1, all equal, negatives, `long long` overflow (**use `long long` whenever products/sums can exceed 2e9**), multiple test cases (**reset globals!**, sum of n constraint).
- Fast IO: `ios::sync_with_stdio(false); cin.tie(nullptr);`

---

## 4. Interviews & OAs in the AI era (what changed)
- **OAs** (HackerRank/HackerEarth/Codility/Mettl) are the first filter at almost every company visiting IITs for internships. Typically 2–4 problems in 60–90 min, at roughly **CF 1200–1800 level** (quant/HFT and top product firms at the upper end). Proctoring now commonly includes webcam, tab-switch detection and **AI-similarity checks**, so solutions that look LLM-generated get flagged. Your own speed is what counts.
- **Codeforces itself restricts AI tool usage during rated rounds** (rules updated since 2024, so read the current rule post). Respect it. Your rating is a credential, and AI-assisted ratings get rolled back.
- **Live interviews** ask you to talk through brute force → better → optimal, state complexity, write clean code, and dry-run a test. Some companies now let you use AI but grade how you **spec, test, and critique** its output. Practice explaining *why* a solution is correct (an invariant or exchange argument), not just that it passes.
- **Quant/HFT firms** (Graviton, Quadeye, Tower, Optiver, APT, NK Securities, AlphaGrep, Jane Street, Citadel) add **probability/puzzles/mental math** rounds. Resources: *Heard on the Street* (Crack), *50 Challenging Problems in Probability* (Mosteller), *A Practical Guide to Quantitative Finance Interviews* (Xinfeng Zhou), Ch. 2–4. Worth starting next semester, since it pairs with your order book/FPGA projects.

---

## 5. Resources (priority order)

**Practice sets (pick ONE main structured set + CF contests)**
1. **CP-31 sheet (TLE Eliminators)**: 31 curated Codeforces problems per rating band (800 → 1900). Popular among Indian students for exactly your situation. Finish the **1300, 1400, 1500** bands this month (~93 problems). Free.
2. **CSES Problem Set (cses.fi/problemset)**: classic problems per topic. Do: *Introductory* (selectively), *Sorting and Searching* (most of it, high ROI), *Dynamic Programming* (first ~12), *Graph Algorithms* (first ~10).
3. **USACO Guide (usaco.guide)**: **Silver** section (prefix sums, two pointers, binary search, greedy with sorting, DFS/BFS, floodfill, intro to trees), then **Gold** (DP, DSU, shortest paths, topo sort). Each module has explanations + graded problems. Best structured *learning* resource.
4. **TheScrasse's "CF Roadmap"** (Codeforces blog, search the title): ~100 problems from AtCoder/CF aimed at reaching blue. A good alternative to CP-31.
5. **AtCoder Beginner Contests** (atcoder.jp). Practice C/D/E of past ABCs via AtCoder Problems (kenkoooo.com/atcoder) with difficulty colours.

**Learning / reference**
6. **Antti Laaksonen, *Competitive Programmer's Handbook*** (free PDF; the CSES author). Ch. 3 (sorting), 4 (data structures), 5 (complete search), 6 (greedy), 7 (DP), 8 (amortized analysis, i.e. two pointers), 11–13 (graphs basics), 14 (tree algorithms), 15 (spanning trees), 21–22 (number theory, combinatorics). Compact and excellent.
7. **CP-Algorithms (cp-algorithms.com)**: the reference for any specific algorithm (binary exponentiation, sieve, modular inverse, DSU, Dijkstra, segment tree).
8. **YouTube:** **Errichto** (problem-solving process, binary search, DP), **Colin Galen** (mindset, "how to practice", greedy/observations), **Priyansh Agarwal** and **TLE Eliminators** (Indian context, CF editorial-style), **William Lin** (contest screencasts, good for seeing speed).
9. **Codeforces EDU section** (codeforces.com/edu): interactive courses on **binary search**, **two pointers**, DSU, segment trees, with practice problems. The binary search and two pointers courses are perfect for Tier 1.

**Interview DSA (last week of break + next semester)**
10. **Striver's A2Z DSA sheet** (takeuforward.org) or **NeetCode 150** (neetcode.io, with video explanations). Pick one. Do the linked list, tree, heap, trie, backtracking and design sections, which CF doesn't cover.
11. **LeetCode weekly/biweekly contests**: good OA simulation (timed, interview-style).

---

## 6. 30-day plan

| Week | Focus | Targets |
|---|---|---|
| 1 | Tier 1: sorting/greedy, prefix sums, two pointers, **binary search on answer**, stress testing setup | CF EDU binary search + two pointers (steps 1–2), CP-31 1300 band, 2–3 contests |
| 2 | Math (mod, sieve, nCr, gcd), constructive, bits | CP-31 1300 done + 1400 half, CSES Sorting & Searching, 2–3 contests |
| 3 | Graphs (BFS/DFS/Dijkstra/topo/DSU), trees | USACO Silver graph modules, CP-31 1400 done, 2–3 contests |
| 4 | DP basics + interview topics (linked list, heap, trie, LRU) | CSES DP first 10, CP-31 1500 half, Striver/NeetCode linked-list + heap sections, 2–3 contests |

Track everything in `codeforces_dsa/log.md`: date, problem, rating, solved/not, time, key observation. After 30 days you'll have ~100 logged problems and a clear map of weak tags.

---

## 7. Self-check: you're ready for 1600 when you can
- Explain why binary search on the answer works and write it bug-free (lo/hi invariants) in 3 minutes
- Compute nCr mod p for n ≤ 2e5 in O(1) per query after O(n) precomputation
- Write BFS, DFS, Dijkstra and DSU from memory without bugs
- Solve a Div2 B within 15 minutes ~80% of the time
- Stress-test a WA solution in < 5 minutes
