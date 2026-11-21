# NASDAQ ITCH 5.0 Parser on FPGA — Theory

> Goal: an RTL (SystemVerilog) block that takes a byte stream of NASDAQ ITCH 5.0 messages (from a file in simulation, later from UDP/MoldUDP64) and outputs decoded fields (type, order ref, side, shares, price, …) with deterministic latency of a few clock cycles. It's verified against your C++ parser from `order_book/` as the golden model.

Why FPGAs in trading: a CPU path (NIC → kernel/bypass → parse → decide → send) costs ~1–5 µs. On an FPGA, the network PHY feeds logic directly, so parse+decide can take **tens of ns** with *deterministic* latency. Every serious HFT shop (Jump, Optiver, IMC, Citadel Securities, Tower, Graviton, Quadeye…) hires FPGA engineers, and "market data feed handler in RTL" is *the* canonical project.

---

## 1. The protocol stack (what bytes arrive)

```
 Ethernet (14 B) │ IPv4 (20 B) │ UDP (8 B) │ MoldUDP64 header (20 B) │ [len(2) │ ITCH msg] [len(2) │ ITCH msg] ...
```
- **MoldUDP64** (NASDAQ's packet framing for multicast): `Session` (10 B ASCII) + `Sequence Number` (8 B, number of the first message in the packet) + `Message Count` (2 B). Then message blocks, each a **2-byte length** + the message. Sequence numbers let you detect **gaps** (packet loss), which is an interview topic. Recovery goes through a request/retransmit server.
- **SoupBinTCP**: the TCP equivalent (used for order entry/OUCH and some replay). Just know it exists.
- **The sample file** from `emi.nasdaq.com/ITCH/Nasdaq ITCH/` = the same `[len(2) | msg]` blocks back to back, with no UDP/Mold headers. **Start with the file.** It's the payload of the network stack.

### ITCH 5.0 essentials
- **All integers big-endian.** Alpha fields are ASCII, left-justified, space-padded.
- **Common header (11 bytes):** `Message Type` (1, ASCII char) · `Stock Locate` (2) · `Tracking Number` (2) · `Timestamp` (6, ns since midnight).
- **Price(4)** = `uint32` with 4 implied decimals ($123.45 → 1234500). **Price(8)** has 8 decimals (MWCB only).

| Type | Message | Length (bytes) | Fields after the 11-byte header |
|---|---|---|---|
| `S` | System Event | 12 | event code (1) |
| `R` | Stock Directory | 39 | stock(8), market category, … |
| `H` | Stock Trading Action | 25 | stock(8), state, reserved, reason(4) |
| `A` | **Add Order** | **36** | order ref(8), side(1 'B'/'S'), shares(4), stock(8), price(4) |
| `F` | Add Order w/ MPID | 40 | as A + attribution(4) |
| `E` | **Order Executed** | **31** | order ref(8), executed shares(4), match number(8) |
| `C` | Order Executed w/ Price | 36 | as E + printable(1), execution price(4) |
| `X` | **Order Cancel** | **23** | order ref(8), cancelled shares(4) |
| `D` | **Order Delete** | **19** | order ref(8) |
| `U` | **Order Replace** | **35** | original ref(8), new ref(8), shares(4), price(4) |
| `P` | Trade (non-cross) | 44 | order ref, side, shares, stock, price, match no. |
| `Q`, `B`, `I`, `N`, `Y`, `L`, `V`, `W`, `K`, `J`, `h`, `O` | Cross trade, broken trade, NOII, RPII, Reg SHO, MPID position, MWCB, IPO, LULD, operational halt, DLCR | various | parse the length, can skip contents |

**Always verify lengths and offsets against the official spec PDF.** Don't trust this table (or an AI) blindly. Writing a tiny Python script that asserts `sum(field sizes) == length` for every message type is a good first task.

**Key design insight:** every message's length is known from its type byte, *and* it's given by the 2-byte length prefix anyway. So the parser never needs to scan for delimiters. That's why ITCH is FPGA-friendly.

---

## 2. Digital design / Verilog ramp (≈ 2 days)

You're ECE, so you likely know gates and FSMs from coursework. The new part is **writing synthesizable RTL like a hardware engineer**.

### Must-know concepts
| Concept | What to know |
|---|---|
| Combinational vs sequential logic | `always_comb` vs `always_ff @(posedge clk)` |
| **Blocking (`=`) vs non-blocking (`<=`)** | `<=` in sequential, `=` in combinational. Mixing them causes sim/synth mismatches (Cummings' paper, see resources). |
| Registers, enables, synchronous reset | Default to synchronous active-high or active-low resets. Be consistent. |
| **FSMs** | Moore vs Mealy, one-hot vs binary encoding, two-process style |
| **Pipelining** | Split long combinational paths with registers. Latency ↑, Fmax ↑, throughput stays 1/cycle. |
| **Timing** | Setup/hold, critical path, Fmax, slack, timing closure. "Logic levels" per stage. |
| **Valid/ready handshake** | Transfer happens when `valid && ready`. Backpressure. **AXI4-Stream**: `tdata`, `tvalid`, `tready`, `tkeep` (which bytes are valid), `tlast` (end of packet). |
| FIFOs | Sync FIFO; **async FIFO with Gray-code pointers** for clock domain crossing |
| **CDC (clock domain crossing)** | Metastability, 2-flop synchronizer for single bits, async FIFO for buses. **Asked in every FPGA interview.** |
| FPGA resources | LUTs, FFs, BRAM, DSP slices, carry chains. What maps to what. |
| Endianness & byte lanes | Big-endian ITCH on a little-endian-lane bus: byte 0 of the message is in which bits of `tdata`? Decide once, document it. |

### Tools (all free, all run on your Mac or a Linux VM)
- **Verilator** (fast, SystemVerilog lint + sim) or **Icarus Verilog** (simpler, slower). Use `brew install verilator icarus-verilog`.
- **cocotb**: write testbenches **in Python**. You're strong in Python, so this is a big win. Your testbench reads the real ITCH file, drives bytes in, and compares outputs with a Python/C++ reference.
- **GTKWave** or **Surfer** for waveforms.
- **Vivado** (Xilinx/AMD, Linux/Windows only, free WebPACK edition) for synthesis + timing reports when you want real Fmax/LUT numbers. Use the IITG lab or a VM. Open-source alternative: **Yosys + nextpnr** for Lattice iCE40/ECP5.
- Do you own a board? **Not required.** Simulation + a synthesis report (Fmax, LUTs) is a complete, credible project. Common boards if you get access: Digilent Basys 3 / Arty A7 (Artix-7), and for networking, boards with SFP+/Ethernet.

---

## 3. The core hardware problem: unaligned messages on a wide bus

A 10 GbE MAC typically gives you a **64-bit (8-byte) AXI-Stream at 156.25 MHz**. ITCH messages are 12–50 bytes and start at **any byte offset** within an 8-byte beat. Example: a 36-byte Add Order followed by a 19-byte Delete:

```
beat 0: [len len A  loc loc trk trk ts ]
beat 1: [ts ts ts ts ts ref ref ref    ]
...
beat 4: [... price price | len len D loc]  <- message boundary mid-beat
```
Design approaches (pick one, explain why in your README):
1. **Byte-serial** (1 byte/cycle). Trivial FSM with a byte counter. Easy, but 8× too slow for 10G at 156 MHz. **Good v0.**
2. **Shift-register / realignment buffer**: accumulate bytes into a buffer wide enough for the longest message (50 B = 400 bits). When `count ≥ msg_len`, emit the whole message in parallel and shift out the consumed bytes. Needs a barrel shifter (muxes = LUTs = timing pressure).
3. **Per-type field extraction in parallel**: once a full message is aligned, every field sits at a fixed offset for that type, so extraction is just wires + a mux on type. Output a wide struct: `{type, locate, ts, ref, side, shares, price, new_ref, ...}` with `valid`.
4. **Multiple messages per beat** (stretch): two short messages can end and start in the same 8-byte beat. Handling >1 message/cycle is the "advanced" version and a great interview story.

**Metrics:** latency (cycles from last byte of message in → decoded valid out), throughput (bytes/cycle sustained), Fmax, LUT/FF usage.

---

## 4. Scope options (pick one when you start; I recommend B then C)

| Option | What you build | Effort | Signal |
|---|---|---|---|
| **A. Byte-serial parser (sim only)** | FSM, 1 B/cycle, outputs decoded Add/Exec/Cancel/Delete/Replace. cocotb test against the real file. | ~1 week incl. Verilog ramp | Solid beginner project |
| **B. 64-bit AXI-Stream parser** | Realignment buffer, ≥1 msg/cycle, MoldUDP64 header parse + sequence gap detection, synthesized in Vivado/Yosys with Fmax reported | ~1.5–2 weeks | **Strong. This is the resume line.** |
| **C. B + on-chip top-of-book** | Hash table in BRAM (order ref → {price, qty, side, locate}) + per-symbol best bid/ask registers for a few symbols. Emit BBO updates. | +1–2 weeks | Very strong ("tick-to-BBO in N ns") |
| **D. Full stack** | Ethernet MAC/PHY → IP/UDP (use Alex Forencich's `verilog-ethernet`) → Mold → ITCH on a real board, fed from a PC replaying pcap | needs hardware + time | Excellent but likely next semester |

For C, the on-chip book is the hard part: BRAM has 1–2 cycle read latency, so back-to-back messages to the same order cause **read-after-write hazards**. You need forwarding/bypass logic, just like a CPU pipeline. Great interview material.

---

## 5. Verification strategy (this is what makes it credible)

1. **Golden model:** your C++ (or Python) ITCH parser from `order_book/` produces the expected decoded stream (CSV/JSON).
2. **cocotb testbench:** reads the same file, drives bytes into the DUT with **random `tvalid` gaps and random `tready` backpressure**, captures outputs, and diffs them against the golden model. Run on millions of messages.
3. **Directed tests:** each message type at every byte alignment (0–7), back-to-back short messages, max-length messages, packet boundaries.
4. **Assertions (SVA):** `valid` held until `ready`, data stable while stalled, no output without input.
5. Stretch: **formal verification** with SymbiYosys (ZipCPU's tutorials) to prove handshake properties.
6. Report: "verified on N million messages from the NASDAQ sample day with randomized backpressure, zero mismatches."

---

## 6. Interview questions

**FPGA/RTL fundamentals**
1. Blocking vs non-blocking. What goes wrong if you mix them?
2. What is metastability? How does a 2-FF synchronizer help? Why not for multi-bit buses?
3. Design an async FIFO. Why Gray code pointers? How do you generate full/empty?
4. Setup vs hold violation. Which one can you fix by lowering the clock? (Setup only.)
5. How do you increase Fmax? (Pipeline, retime, reduce fan-out, reduce logic levels.)
6. Latency vs throughput in a pipeline. Can you have 1 msg/cycle throughput with 5 cycles latency? (Yes.)
7. Explain AXI-Stream handshake and backpressure. Can `tvalid` depend on `tready`? (No, AXI rule: a source must not wait for ready before asserting valid.)
8. What do LUTs, FFs, BRAMs and DSPs implement? Would a 50-byte barrel shifter be expensive?
9. Write an FSM in SystemVerilog on a whiteboard (e.g. a sequence detector).

**Trading-specific**
10. Why do HFT firms use FPGAs? What's tick-to-trade latency?
11. How do you detect and handle a dropped UDP packet in MoldUDP64? (Sequence gap → request retransmission / arbitrate between redundant A/B feeds.)
12. Why is ITCH big-endian on the wire, and what does that mean for your byte lanes?
13. How would you maintain an order book in hardware? Hash collisions? Read-after-write hazards?
14. A/B feed arbitration: the same data arrives on two multicast lines. How do you dedupe? (By sequence number, take the first.)

**AI-era probes**
- "How did you verify this?" A good answer is a golden-model diff on real data plus randomized backpressure, with assertions.
- "Here's a waveform, find the bug" (a dropped beat when `tready` deasserts at the same cycle a message ends). Practice reading your own waveforms.
- HLS (Vitis HLS, C++ → RTL) vs hand-written RTL: when would you use each? Firms use both. Hand-written RTL wins on latency control.

---

## 7. Resources (priority order)

1. **NASDAQ TotalView-ITCH 5.0 Specification (PDF, nasdaqtrader.com)**. §1–3 (architecture, data types) and §4 (message formats). Keep it open the whole project. **Also the MoldUDP64 spec PDF** (same site, ~5 pages).
2. **Sample data:** `emi.nasdaq.com/ITCH/Nasdaq ITCH/` (e.g. a `*.NASDAQ_ITCH50.gz` day file). It's huge, so take the first 10–100 MB for tests.
3. **HDLBits (hdlbits.01xz.net)**. Do the sections: Verilog Language (all), Circuits → Sequential Logic → Latches and FFs, Counters, Shift Registers, **Finite State Machines** (do ~15 FSM problems, including the "serial receiver" ones, which are basically byte-protocol parsers). ~1 day.
4. **Harris & Harris, *Digital Design and Computer Architecture***. Ch. 3 (sequential logic, timing, metastability, §3.5 synchronizers) and Ch. 4 (HDL), as a refresher.
5. **Clifford Cummings (Sunburst Design) papers** (free PDFs): "Nonblocking Assignments in Verilog Synthesis, Coding Styles That Kill!", "Clock Domain Crossing (CDC) Design & Verification Techniques Using SystemVerilog", "Simulation and Synthesis Techniques for Asynchronous FIFO Design". Interview classics.
6. **ZipCPU blog (zipcpu.com)**. Posts on AXI-Stream / handshaking ("Strategies for pipelining", the skid buffer post) and formal verification with SymbiYosys. The skid buffer post is a must-read for valid/ready.
7. **cocotb docs** (docs.cocotb.org). Quickstart + "Writing Testbenches". Plus Verilator's cocotb integration.
8. **Reference RTL to read (don't copy):** `Essenceia/ITCH` (RTL ITCH 5.0 decoder with auto-generated message outputs, pairs with a MoldUDP64 module), `LaSaber/Nasdaq-HFT-FPGA` (Icarus Verilog decoder + testbench replaying NASDAQ dumps, MoldUDP64, OUCH). Both are CC BY-NC. **Columbia CSEE 4840 (Spring 2026) "Market Data Parser" design doc** (DE1-SoC, ITCH parsing + order hash table in fabric). Excellent for option C.
9. **Alex Forencich, `verilog-ethernet` / Corundum (GitHub)**. The standard open-source 1G/10G Ethernet + IP/UDP stack, for option D.
10. **Nandland (nandland.com)**. Beginner-friendly FPGA explanations if HDLBits feels too terse. r/FPGA has a good wiki/FAQ on getting started.

---

## 8. Metrics / resume line

> "SystemVerilog NASDAQ ITCH 5.0 + MoldUDP64 decoder on a 64-bit AXI-Stream: **1 message/cycle at X MHz** (Artix-7 / Vivado), **N-cycle (≈ Y ns) latency**, sequence-gap detection. Verified with cocotb against a C++ golden model on Z million real NASDAQ messages under randomized backpressure."
