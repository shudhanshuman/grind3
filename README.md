# grind3 — Winter Break 2026 (≈30 days)

Seven tracks, one per folder. Each folder has a `theory.md` that covers what to learn **before** you code: concepts, design decisions, interview questions (classic and AI-era), and specific resources (with the exact chapters/sections to read).

| # | Folder | Project | Main language | Story it tells a recruiter |
|---|---|---|---|---|
| 1 | `vector_db/` | Vector database (HNSW + IVF-PQ + persistence) | C++ (or Rust) | "I understand the infra under RAG / LLM apps" |
| 2 | `order_book/` | Limit order book + matching engine | C++ | "I write low-latency systems code" (HFT/quant) |
| 3 | `itch_fpga/` | NASDAQ ITCH 5.0 parser on FPGA | SystemVerilog | "I do hardware for trading" (FPGA/HFT) |
| 4 | `compiler/` | Your own compiler | C / C++ / Python | "I understand languages, IR, codegen" (ML compilers too) |
| 5 | `neural_accelerator/` | One piece of an NPU (options inside) | SystemVerilog + Python | "I understand AI hardware" (NVIDIA/Qualcomm/AMD/startups) |
| 6 | `chess_engine/` | Finish the chess engine (from zero theory) | C++ engine + your PyGame UI | Search, game trees, NNUE / AlphaZero |
| 7 | `codeforces_dsa/` | 1330 → 1600+ and interview DSA | C++ | Clears the OA, which is the first filter for every company |

---

## Be honest about the time budget

You have about 30 days, call it 8–10 focused hours a day, so 250–300 hours. Rough honest estimates for a version you'd be proud to put on a resume:

| Project | Theory | Build (resume-grade v1) | Notes |
|---|---|---|---|
| Codeforces/DSA | ongoing | **1.5–2 h every day** (≈50 h) | Never skip. This is what gets you through the OA. |
| Order book | 6–8 h | 30–40 h | Also your C++ ramp-up |
| ITCH on FPGA | 10–12 h (Verilog basics included) | 40–50 h | Reuses the order book. Same HFT story. |
| Chess engine | 8–10 h | 40–60 h | Perft-correct move generation is the hard 50% |
| Vector DB | 6–8 h | 30–40 h | |
| Compiler | 8–10 h | 40–60 h | |
| Neural accelerator | 8–10 h | 40–50 h | Shares the Verilog ramp with ITCH |

**Total ≈ 330–420 h. That is more than one month.** My recommendation:

- **Core (finish these properly):** Codeforces daily, then **Order book → ITCH FPGA** (one HFT story: hardware feed parser drives a software book), then the **Chess engine** (already started; it's your most fun one).
- **Stretch (pick 1, maybe 2):** Vector DB (best fit for AI/ML roles) *or* the Neural accelerator (best fit for hardware/AI-chip roles). The compiler can roll into next semester, or merge it with the accelerator: a tiny compiler that lowers a model onto your accelerator is a killer combined project.

Two finished, benchmarked, well-written-up projects beat seven 60%-done repos. Interviewers ask "what was the hardest bug / what did you measure?", and you only have good answers for finished work.

### Suggested order (adjust freely)

```
Every day:   1.5–2h Codeforces (see codeforces_dsa/theory.md for the routine)

Days 1–2    C++ ramp (below) + order_book theory
Days 3–8    Order book: correct → benchmarked → optimized → ITCH file replay
Days 9–10   Verilog/FPGA ramp (in itch_fpga/theory.md §2)
Days 11–17  ITCH parser in RTL, verified against your C++ parser (golden model)
Days 18–26  Chess engine: board → perft → search → eval → UCI → (NNUE stretch)
Days 27–30  Stretch project v0 (vector DB or accelerator) + READMEs, blog posts, resume lines
```

---

## Shared prerequisite: C++ ramp (you know Python/JS)

Four of the seven projects want C++. Do this in ~1.5 days, not more. Learn the rest while building.

**learncpp.com, these chapters only:** 1–5 (basics, skim), 9 (references/pointers), 12 (compound types, references), 13–14 (enums, structs, classes), 15 (more classes), 16–17 (`std::vector`, `std::array`), 19 (dynamic allocation), 22 (move semantics and smart pointers), 26 (templates, skim). Chapter numbers shift a bit between site revisions. Go by topic names.

Must-know list:
- Stack vs heap, RAII, `unique_ptr`, and why the hot path should **never** call `new`
- References vs pointers, `const` correctness, pass-by-reference for big objects
- Move semantics (`std::move`, rvalue references) at the level of "when does a copy happen?"
- STL: `vector`, `array`, `unordered_map`, `map`, `deque`, `priority_queue`, and their complexity and **memory layout** (contiguous vs node-based)
- Undefined behaviour: out-of-bounds, signed overflow, use-after-free. Always build debug with `-fsanitize=address,undefined`.
- Build tooling: **CMake** (one `CMakeLists.txt` per project), `-O2/-O3 -march=native`, a debugger (`lldb` on Mac)
- Testing: GoogleTest or Catch2. Benchmarks: Google Benchmark.

**Mac M2 notes:** Apple clang is fine. `perf` doesn't exist on macOS. Use Instruments (Time Profiler, counters) or `samply`. For Linux-only stuff (HFT kernel tricks, Verilator speed), use a Linux VM/Docker or an IITG lab machine. Your CPU is ARM64 (cache line is **128 B on Apple M-series**, vs 64 B on x86). That matters for false-sharing padding, so mention it in interviews.

---

## How interviews have changed in the AI era (applies to every folder)

1. **The OA is still the gate, but more of it is proctored.** Codeforces-style OAs (HackerRank, HackerEarth, Codility) now have webcam and screen monitoring and plagiarism/AI-similarity checks. Many firms (especially quant/HFT in India: Graviton, Quadeye, Tower, Optiver, APT, NK Securities, AlphaGrep, etc.) moved more rounds back to live or in-person interviews. Raw DSA ability matters *more* now, not less.
2. **"Walk me through your project" got harder.** Interviewers assume any repo could be AI-generated, so they probe: *why* this data structure, what you measured, what broke, what you'd change, what the alternative was. Every theory.md has a "defend your design" list. Make sure you can answer it without notes.
3. **Code-reading and debugging rounds.** You're given AI-written or buggy code and asked to find the bug, the performance problem or the race. Projects where *you* hit the bugs (perft mismatches, CDC glitches, use-after-free in a pool allocator) are your training data.
4. **Using AI is allowed in some rounds.** Some companies now run "AI-assisted" rounds where you can use Copilot/Claude, and they grade how well you specify, verify and test. The skill is: write the spec and tests yourself, let AI draft, verify with a golden model. That is exactly the workflow in these projects (C++ model ↔ RTL, python-chess ↔ your perft, FAISS ↔ your recall).
5. **Numbers beat adjectives.** "p99 add-order latency 85 ns", "recall@10 = 0.95 at 12k QPS on SIFT1M", "perft(6) correct, 1.2 M nps", "parses one ITCH message per cycle at 250 MHz". Every theory.md ends with the metrics you should report.

**My role when you build:** you write the core logic. I'll explain, review, write test harnesses and golden models, help debug, and pair-program when you're stuck. For learning projects, the bugs you fix yourself are the point.
