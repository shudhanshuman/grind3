# Limit Order Book (LOB) + Matching Engine — Theory

> Goal: a C++ limit order book that (a) matches orders like an exchange and (b) rebuilds the real NASDAQ book from an ITCH 5.0 file. It should be benchmarked with latency percentiles. This is the software half of your HFT story. `itch_fpga/` is the hardware half.

---

## 0. Why this project matters

- It's the **#1 most common systems-design question at HFT/quant firms**: "Design an order book. What data structures? What's the complexity of add/cancel/execute? How do you make it fast?"
- It forces you to learn the things those firms test: cache behaviour, memory allocation, branch prediction, data layout, latency measurement.
- It's AI-proof in interviews. The follow-ups are about *measured* trade-offs, which you only know if you built and profiled it.

---

## 1. Market microstructure (what the book represents)

**Read first:** Larry Harris, *Trading and Exchanges*, Ch. 1–6 (orders, market structure, order-driven markets). If short on time: Ch. 4 (orders and order properties) and Ch. 6 (order-driven markets).

| Term | Meaning |
|---|---|
| **Bid / Ask (offer)** | Buy orders / sell orders resting in the book |
| **Best bid / best ask (BBO, top of book)** | Highest bid price, lowest ask price |
| **Spread** | best ask − best bid |
| **Mid price** | (best bid + best ask)/2. Microprice = size-weighted variant. |
| **Tick size** | Minimum price increment (US stocks ≥ $1: $0.01) |
| **Lot / shares / qty** | Order size |
| **Price level** | All resting orders at one price on one side |
| **Depth** | Aggregate quantity at each level |
| **L1 / L2 / L3 data** | L1 = BBO only. L2 = aggregated qty per price level. L3 = every individual order (ITCH is L3). |
| **Maker / taker** | Maker adds liquidity (rests in book). Taker removes it (crosses the spread). |
| **Crossed / locked book** | bid > ask / bid == ask (shouldn't persist on one venue) |

### Order types you should implement (in this order)
1. **Limit order**: buy/sell up to qty at price P or better. The unfilled remainder rests.
2. **Market order**: take whatever is available at any price. Never rests.
3. **Cancel**: remove a resting order by id.
4. **Modify / replace**: change price or qty. **Priority rule** (standard at most exchanges): reducing qty *keeps* time priority. Increasing qty or changing price *loses* it (treated as cancel + new).
5. **Time-in-force:** **GTC** (rests until cancelled), **IOC** (fill what you can now, cancel the rest), **FOK** (fill entirely now or do nothing, so you need a liquidity check first).
6. Stretch: **post-only** (reject if it would take), **iceberg** (displayed vs hidden qty), **stop / stop-limit** (trigger on last trade price).

### Matching rules
- **Price-time priority (FIFO):** better price first. At the same price, earlier order first. NASDAQ and most equities use this. **Implement this.**
- **Pro-rata:** at a price level, fills are split proportional to size (some futures markets). Good interview talking point.
- A trade happens at the **resting (maker) order's price**, not the aggressor's.
- An incoming order **sweeps** levels: matches the best opposite level, then the next, until it's filled or the price no longer crosses.

### Two kinds of order book (important distinction)
| | **Exchange matching engine** | **Feed-handler book (market data)** |
|---|---|---|
| Who | The exchange | Every trading firm |
| Input | Orders from participants | Exchange messages (ITCH: Add, Execute, Cancel, Delete, Replace) |
| Does matching? | **Yes** | **No.** The exchange already matched. You just *apply* events. |
| Hot ops | add, match, cancel | add, reduce, delete by order id; read BBO |

Build **both modes** on the same data structure. Mode B is what HFT firms actually run, and you feed it real NASDAQ data from `itch_fpga/`.

---

## 2. Data structures (the heart of the interview)

### Operations & target complexity
| Operation | Target |
|---|---|
| Add order at existing level | O(1) |
| Add order at new level | O(log L) tree, or O(1) array |
| Cancel / delete by order id | **O(1)** |
| Execute against best level | O(1) per fill |
| Get best bid/ask | **O(1)** |
| Get depth at price | O(1) |

### Canonical design
```
Order        { id, side, price, qty, timestamp, prev*, next*, level* }   // intrusive list node
PriceLevel   { price, total_qty, count, head*, tail* }                   // FIFO queue of orders
Side (bids)  : price -> PriceLevel   (sorted; best = max)
Side (asks)  : price -> PriceLevel   (sorted; best = min)
OrderIndex   : order_id -> Order*    (hash map) — this gives O(1) cancel
```
- **Intrusive doubly linked list** per level: the `prev/next` pointers live *inside* the Order, so unlinking on cancel is O(1) and allocates nothing.
- **Hash map id → Order\***: O(1) lookup for cancel/execute. `std::unordered_map` is slow (node-based, one allocation per insert). Use an **open-addressing** map (linear probing, e.g. `ankerl::unordered_dense`, `absl::flat_hash_map`), or a plain `vector` indexed by id if ids are dense.

### Price-level container: the big trade-off
| Option | Pros | Cons |
|---|---|---|
| `std::map<Price, Level>` (red-black tree) | Simple, handles any price | Node allocation, pointer chasing, cache misses, O(log L) |
| **Dense array indexed by tick** (`levels[price - base]`) + cached best index | O(1) everything, contiguous | Needs bounded price range. Finding the next best after a level empties = scan (use a bitmap + `ctz`/`clz` to jump) |
| Sorted `vector` of levels, **best at the back** | Most activity is near the top, so insert/erase near the back is cheap. Great cache locality. | O(L) worst case insert |
| Hybrid: array window around the mid + map for far-away prices | Best of both | More code |

Real-world insight (David Gross, Optiver, CppCon 2024): a typical stock book has ~1000 levels per side, but **almost all activity is within a few levels of the top**. So a sorted vector with best-at-the-end, searched linearly from the top, beats a tree in practice. **Benchmark map vs vector vs array yourself.** That benchmark table *is* your resume line.

### Memory
- **Object pool / free list** for Orders: preallocate N orders in a `vector`, hand out indices, recycle on delete. Zero `malloc` on the hot path.
- Prefer **indices (uint32) over pointers**: smaller nodes, and the pool can be relocated.
- **Struct layout:** put hot fields together, keep Order ≤ 64 B (one x86 cache line), avoid `bool` padding waste. Check with `sizeof` and `static_assert`.
- **Prices as integers** (ticks, or ITCH's 4-implied-decimal `uint32`). **Never use floating point for prices.** Interviewers ask this.

---

## 3. Low-latency C++ concepts you need

| Concept | One-line version | Where it shows up |
|---|---|---|
| **Cache hierarchy** | L1 ~1 ns, L2 ~4 ns, L3 ~15 ns, DRAM ~80–100 ns. A cache miss costs far more than arithmetic. | Why array beats map |
| **Cache line** | 64 B on x86, 128 B on Apple M. Unit of transfer. | Struct sizing, false sharing |
| **Spatial/temporal locality** | Contiguous + reused data is fast | vector vs list |
| **Branch prediction** | Mispredict ≈ 15–20 cycles. Make the common path predictable. `[[likely]]` and `[[unlikely]]` exist. | Side checks, rare order types |
| **Allocation cost** | `malloc` can take 100s of ns and has unpredictable tails | Pools |
| **Virtual dispatch** | Indirect call, blocks inlining | Use templates/CRTP or `std::variant` |
| **Inlining / `-O3` / LTO / PGO** | Compiler does a lot if you let it | Build flags |
| **False sharing** | Two threads write different vars on the same cache line, so the line ping-pongs | `alignas(64/128)` padding |
| **Lock-free SPSC ring buffer** | One producer, one consumer, `std::atomic` head/tail with acquire/release ordering | Feed thread → strategy thread |
| **Memory ordering** | `relaxed` / `acquire` / `release` / `seq_cst` | Must be able to explain acquire/release |
| **Tail latency** | p99/p99.9 matter more than the mean in trading | How you report results |
| **Kernel bypass** (just know it exists) | DPDK, Solarflare/AMD Onload/ef_vi, busy polling, CPU pinning, isolcpus, hugepages | "How would you go further?" |

### Measuring latency correctly
- Use `std::chrono::steady_clock`, or `rdtsc` (x86) / `cntvct_el0` (ARM) for cycle counts. Measure **per operation**, record into a histogram, report p50/p90/p99/p99.9/max.
- **Warm up** first (caches, branch predictors, page faults). Pin to a core on Linux.
- Beware the compiler optimizing your benchmark away (`benchmark::DoNotOptimize`).
- Throughput (msgs/sec over a whole file replay) *and* latency per op are separate metrics. Report both.

---

## 4. ITCH replay (connects to project 3)

NASDAQ publishes free sample full-day ITCH 5.0 files (several GB, gzipped) at `emi.nasdaq.com/ITCH/Nasdaq ITCH/`. File format: each message = **2-byte big-endian length + message bytes**. Messages you need for the book:

| Type | Name | Book action |
|---|---|---|
| `R` | Stock Directory | map `stock_locate` → symbol |
| `A` / `F` | Add Order (no MPID / with MPID) | insert order (ref, side, shares, price) |
| `E` | Order Executed | reduce qty by executed shares; delete if 0 |
| `C` | Order Executed With Price | same as E (price differs, for trade print) |
| `X` | Order Cancel | reduce qty by cancelled shares |
| `D` | Order Delete | remove order |
| `U` | Order Replace | delete original ref, add new ref with new price/qty (same side, same stock) |
| `P` | Trade (non-cross) | hidden-order trade, no book change |

All integers are **big-endian**. Prices are `uint32` with 4 implied decimals. Timestamps are 6-byte ns since midnight. Full field layouts are in `itch_fpga/theory.md` §1.

Plan: write the **software ITCH parser in C++ first**. It becomes the **golden reference model** for the FPGA parser, and the event source for your book. One parser, two projects.

Validation: after replay, print the top 5 levels of AAPL at some timestamp. Cross-check that the book is never crossed, that no order qty goes negative, and that every E/X/D references an existing order.

---

## 5. Architecture to build

```
 ITCH file ──► mmap'd reader ──► parser (zero-copy, switch on type) ──► Book manager
                                                                       │ per-symbol books (array by stock_locate)
                                                                       ▼
                                                              BBO updates ──► SPSC queue ──► "strategy" thread (prints/records)
```
Milestones:
1. Matching engine (mode A) with unit tests for every order type. Use a tiny text protocol (`B 100 @ 50.10`) for testing.
2. Swap map → array/vector levels, add the pool allocator. Benchmark each version with the same random order stream.
3. Feed-handler mode (B): ITCH replay for one day, all symbols. Report msgs/sec and per-message latency percentiles.
4. Stretch: SPSC queue + second thread, L2 snapshot output, a Python/Matplotlib depth chart of one stock over the day.

---

## 6. Interview questions you should be able to answer

**Classic**
1. Design an order book. Walk through add / cancel / execute / best price complexities.
2. Why a hash map from order id? What happens with `std::unordered_map` under high churn?
3. `std::map` vs array vs sorted vector for price levels. When does each win?
4. Why not floats for prices?
5. How does a market order sweep multiple levels? What about IOC vs FOK?
6. What priority rule applies when an order is modified?
7. What's false sharing? How do you avoid it?
8. Implement a lock-free SPSC queue. Why is acquire/release enough? Why not `seq_cst`?
9. How do you measure latency? Why p99 and not average?
10. Your book takes 500 ns per message. Where do you look first? (Profile, count allocations, cache misses.)
11. How would you handle 8000 symbols? (Array of books indexed by stock_locate. Shard symbols across cores.)
12. Pro-rata vs FIFO matching: what incentives does each create?
13. (Quant flavour) What information does the order book give about short-term price direction? (Order imbalance, microprice.)

**AI-era / "defend your project" probes**
- "Show me your latency histogram. What's causing the tail?"
- "What did you try that *didn't* help?" (Keep a `NOTES.md` log of every optimization with before/after numbers. It's gold for interviews.)
- "Here's an AI-generated order book. Find the bug." (Classic bugs: forgetting to remove an empty level, not updating the best price after a delete, iterator invalidation, a modify that keeps priority on a qty increase, integer overflow in notional.)
- "How did you verify correctness?" (Unit tests, invariants checked after every event in debug builds, cross-check against a naive reference implementation on random streams = **differential testing**.)

---

## 7. Resources (in priority order)

1. **CppCon 2024 keynote, David Gross (Optiver): "When Nanoseconds Matter: Ultrafast Trading Systems in C++"** (YouTube, CppCon channel). Watch the whole thing: order book design, why vectors beat maps, SPSC queues, measuring. ~90 min. *If you watch one thing, watch this.*
2. **CppCon 2017, Carl Cook (Optiver): "When a Microsecond Is an Eternity"** (YouTube). Low-latency C++ techniques: hot path, warming, avoiding allocations/exceptions/virtuals.
3. **valkheim.github.io, "C++ performance: Case study of a limit order book"**. A blog walkthrough of optimizing a LOB, with the dense-array vs map argument. Read it after your v1 works.
4. **"How to Build a Fast Limit Order Book" (WK Selph, 2011, archived blog, widely linked from GitHub repos)**. The classic short post: tree of levels + linked lists + hash map. Read it on day 1. It's short.
5. **Sourav Ghosh, *Building Low Latency Applications with C++* (Packt, 2023)**. Ch. 4 (low-latency building blocks: memory pool, lock-free queue, logger), Ch. 6 (matching engine and order book), Ch. 8 (market data). The code is on GitHub. Use it as a reference implementation, not a copy source.
6. **Jane Street tech talk, Brian Nigito: "How to Build an Exchange"** (YouTube). Architecture of a real exchange: sequencer, matching, market data.
7. **Erik Rigtorp's blog + `rigtorp/SPSCQueue` on GitHub**. A clean, tiny, correct lock-free SPSC queue, plus notes on low-latency tuning.
8. **Larry Harris, *Trading and Exchanges*, Ch. 1–6**. Microstructure concepts (see §1).
9. Reference repos to *read, not copy*: `brprojects/Limit-Order-Book` (C++, market/limit/stop orders), `mattpearson/OrderBook` (map vs RB-tree comparison), `callamd/orderbook` (C++/Rust/Python + a PITCH parser).
10. **NASDAQ TotalView-ITCH 5.0 specification PDF** (nasdaqtrader.com). You'll need §4 (message formats).
11. Communities: r/highfreqtrading, r/quant, r/cpp_questions. The "Low Latency" topic on the Optiver tech blog.

---

## 8. Metrics to report (resume line template)

> "C++20 limit order book + NASDAQ ITCH 5.0 feed handler. Replays a full trading day (≈ X00 M messages) at **N M msgs/s**. Add/cancel/execute p50 **x ns**, p99 **y ns**. Dense-array price levels + pooled intrusive lists were **k× faster than `std::map`** (benchmark included)."

Checklist: unit tests ✔, randomized differential test vs naive book ✔, full-day replay ✔, latency histogram ✔, benchmark table across designs ✔, README with architecture diagram ✔.
