# Neural Accelerator (one piece of an NPU) — Theory

> Goal: design, verify and synthesize **one meaningful block** of a neural network accelerator in SystemVerilog, and run a real (small) quantized model through it, checked against PyTorch bit-exactly. §0 lists the options. Pick one when you get here. §1–6 are the theory common to all of them.
>
> Your edge: you've already *felt* accelerator constraints. On your M2, GQA was slower because of non-contiguous memory and `ffn_dim = 1472` not being a multiple of 128, so matmuls tiled badly on Apple's matrix units. That *is* accelerator design (tile sizes, data layout, memory traffic), seen from the software side. Lead with that story in interviews.

---

## 0. Options

| # | Option | What you build | Effort | Signal / best for |
|---|---|---|---|---|
| **1** | **Systolic-array GEMM engine (mini-TPU)** ⭐ | N×N (4×4 → 8×8 → 16×16) **weight-stationary** int8 MAC array with int32 accumulators, input skew/de-skew logic, on-chip weight/activation buffers (BRAM), a small controller that tiles a big matmul. Runs a quantized MNIST MLP end to end. | 2–3 weeks | The canonical project. Every AI-hardware interviewer knows the TPU. **Most recommended.** |
| **2** | **Conv engine for a tiny CNN** | Line buffers + a 3×3 sliding-window MAC engine (+ ReLU + max-pool) streaming an image. Runs a LeNet-style net on MNIST. | 2–3 weeks | Classic FPGA-vision accelerator. Ties to your YOLO work. Shows streaming dataflow. |
| **3** | **Quantized MLP inference core (end-to-end, small)** | A single MAC/vector unit + FSM sequencing layers + weights in ROM: a complete "draw a digit → FPGA predicts" pipeline (you already built the Python version!). | 1–1.5 weeks | Fastest to *finish*. Less impressive alone. Good if time is short. |
| **4** | **Transformer pieces: softmax / LayerNorm / attention unit** | Hardware softmax (max-subtract, exp via LUT/piecewise-linear, sum, reciprocal) or a fixed-point LayerNorm/RMSNorm, or the QKᵀ → softmax → ·V pipeline for small heads | 2 weeks | **Most aligned with your LLM work. Rare among students.** Non-linear ops are a known hard problem (that's why FlashAttention exists). |
| **5** | **Mini-TPU with an ISA + driver** (Option 1 extended) | Add an instruction set (LOAD_W, LOAD_A, MATMUL, ACT, STORE), a host interface, and a Python driver/compiler emitting instructions → combines with `compiler/` option D | 3–4 weeks | Full-stack NPU story: compiler → ISA → RTL. Biggest payoff, biggest scope. |
| **6** | **RISC-V core + custom MAC/SIMD instruction** | Take a small RISC-V core (e.g. PicoRV32 or your own), add a custom-0 opcode for a dot-product, and compare cycle counts on a matmul in C | 2–3 weeks | Good for CPU/architecture roles. Tests ISA extension understanding. |
| **7** | **HLS-based accelerator (Vitis HLS / hls4ml)** | Write the kernel in C++ with pragmas (pipeline, unroll, array_partition), or compile a Keras/PyTorch model via hls4ml | 1–2 weeks | Fast results. Less "I understand RTL". Fine as a comparison baseline against hand-written RTL. |

My suggestion: **1** (then extend toward **5** if the compiler project goes well), or **4** if you want the LLM angle. Tell me which when you get here.

---

## 1. Why accelerators exist: the numbers

- DNN compute is dominated by **matrix multiplies / convolutions** = huge numbers of **multiply-accumulates (MACs)**. Example: a 1024×1024 GEMM = 1.07 G MACs.
- **Energy is in data movement, not math.** Approximate energy (45 nm, Horowitz ISSCC 2014): 8-bit add ~0.03 pJ, 32-bit float mult ~3.7 pJ, 32-bit SRAM read (small) ~5 pJ, **DRAM read ~640 pJ**. A DRAM access costs ~100–1000× a MAC. → **Maximize reuse of each fetched value on-chip.** Every accelerator design decision follows from this.
- CPUs spend most energy on instruction fetch/decode/control. GPUs amortize that with SIMT. Accelerators remove it with fixed dataflow + huge MAC arrays + software-managed scratchpads (no caches).

### Roofline model (know it cold)
- **Arithmetic intensity (AI)** = FLOPs / bytes moved from memory.
- Attainable perf = **min(peak compute, AI × memory bandwidth)**. Below the "ridge point" you're **memory-bound**, above it **compute-bound**.
- GEMM (n×n): FLOPs 2n³, bytes ~3n²·b, so AI ∝ n → compute-bound for big n. GEMV (batch-1 LLM decoding): AI ≈ 1–2 → **memory-bound**. That's why LLM inference is bandwidth-bound and why KV-cache/quantization matter. You know this from MFU work. Now you get the hardware reason.

---

## 2. Number formats & quantization
- **Fixed point** Qm.n: an integer with an implied binary point. Multiply Qa.b × Qc.d → Q(a+c).(b+d), then shift and round back. Saturate instead of wrapping on overflow.
- **int8 quantization** (affine): `real = scale · (q − zero_point)`. Per-tensor vs **per-channel** scales. Symmetric (zp = 0, simpler hardware) vs asymmetric.
- int8 × int8 → int16 product. Summing K of them needs **int32 accumulators** (log2(K) extra bits of headroom).
- **Requantization:** int32 accumulator → int8 output via `(acc · M) >> shift` where M is a fixed-point multiplier approximating `s_in·s_w/s_out` (Jacob et al. 2018). Implement this exactly, or your hardware won't match PyTorch.
- Post-training quantization (PTQ) vs quantization-aware training (QAT). Newer formats to know: bf16, fp8 (E4M3/E5M2), int4, MX formats (microscaling, shared exponents per block).
- **Bit-exact verification:** write the quantized inference in NumPy with *integer* ops. That's your golden model. RTL must match it bit for bit.

---

## 3. Dataflows and the systolic array
### Loop nest view
GEMM `C[M][N] += A[M][K] · B[K][N]` is 3 nested loops. **Dataflow = which loop is unrolled spatially across PEs and which data stays put.**

| Dataflow | What stays in each PE | Moves | Example |
|---|---|---|---|
| **Weight-stationary (WS)** | one weight | activations flow across, partial sums flow down | Google TPU v1 |
| **Output-stationary (OS)** | one partial sum (accumulates in place) | weights and activations both flow through | many FPGA designs, ShiDianNao |
| **Input-stationary (IS)** | one activation | weights flow, psums flow | — |
| **Row-stationary (RS)** | a row of the conv computation | maximizes reuse of all three for convs | MIT Eyeriss |
| No local reuse | nothing | everything from the global buffer | DianNao |

### Systolic array (WS, how the TPU's MXU works)
- A 2-D grid of **Processing Elements (PEs)**. Each PE = a register holding a weight + a multiplier + an adder + registers to pass data to its neighbours. **Only nearest-neighbour wires**, so it scales to high clock rates. That's the whole point (H.T. Kung, 1978–82).
- Preload weights W[k][n] into the PE grid. Activation rows enter from the left, **skewed** in time (row i delayed by i cycles) so the right values meet. Each PE computes `psum_out = psum_in + a · w`, passes `a` right and `psum_out` down. Results exit the bottom, **de-skewed**.
- Timing: for an N×N array streaming M rows, latency ≈ M + 2N cycles. Throughput = N² MACs/cycle once full. Utilization drops for small M or when the matrix doesn't divide by N (**the M2 `ffn_dim` lesson exactly**).
- **Tiling:** big matmuls are split into N×N weight tiles. The controller loops over tiles, accumulating partial results in an accumulator buffer. Double-buffer the weights (load the next tile while computing the current one) to hide load latency.
- Conv → GEMM via **im2col** (unfold patches into columns), or do the conv natively with line buffers (option 2).

### Memory hierarchy of an accelerator
DRAM → (DMA) → **global buffer / scratchpad SRAM (FPGA BRAM)** → PE-local registers. **Software-managed** (explicit loads), not caches. **Double buffering / ping-pong buffers** overlap transfer with compute. Bandwidth to the array: N activations + N psums per cycle, so BRAM width and partitioning matter.

### Other efficiency tricks (know for interviews)
- **Sparsity:** skip zero weights/activations. Structured 2:4 sparsity (NVIDIA Ampere) vs unstructured (needs index metadata, irregular).
- **Winograd** / FFT convolution: fewer multiplies for 3×3 convs.
- **Operator fusion:** keep intermediates on-chip (matmul → bias → ReLU → requant in one pass).
- Non-linear functions in hardware: LUT + linear interpolation, piecewise-linear approximations, **online softmax** (running max + running sum, the FlashAttention trick, which maps nicely to streaming hardware).

---

## 4. Real-world architectures to know (1–2 sentences each in an interview)
- **Google TPU v1:** 256×256 int8 weight-stationary systolic array (65,536 MACs), 24 MiB unified buffer, CISC-like instructions from the host, ~92 TOPS. Later TPUs: bf16, HBM, inter-chip interconnect, training.
- **NVIDIA Tensor Cores:** small matrix-multiply-accumulate units inside each SM (e.g. 4×4×4 in Volta, larger in later gens), fed by warps. Programmed via WMMA/MMA, CUTLASS, Triton.
- **Apple Neural Engine / AMX:** your M2 has both (ANE via Core ML, AMX matrix coprocessor used by Accelerate/BLAS). Your tiling observations came from these.
- **MIT Eyeriss:** row-stationary dataflow, energy-focused analysis.
- **Berkeley Gemmini:** an open-source systolic-array generator (Chisel) attached to a RISC-V core, with a full software stack. A great reference design.
- **NVDLA:** NVIDIA's open-source inference accelerator RTL.
- Recent: Groq LPU (deterministic, compiler-scheduled, SRAM-only), Cerebras (wafer-scale), Tenstorrent (RISC-V + Tensix cores, open-source software stack), Etched (transformer ASIC), and on-device NPUs (Qualcomm Hexagon, Apple ANE).

---

## 5. Implementation & verification plan (for option 1; others are similar)
1. **Golden model:** train an MNIST MLP (784-128-10) in PyTorch → quantize to int8 → write a **pure-integer NumPy** inference that matches PyTorch's quantized output. Export weights to `.mem`/hex files.
2. **PE module:** registered MAC, parameterized widths. Unit test it with cocotb.
3. **N×N array** with generate loops, input skew shift registers, output de-skew. Test random int8 matrices vs NumPy, including edge values (−128 × −128!) and accumulation overflow headroom.
4. **Buffers + controller FSM:** weight-load phase, stream phase, drain phase. Tile a 784×128 layer onto an 8×8 or 16×16 array. Accumulator buffer for partial sums across K tiles.
5. **Post-processing unit:** bias add + requantize + ReLU.
6. End to end: run 10,000 MNIST test images in simulation (Verilator is fast enough), report accuracy == golden model accuracy and **bit-exact** agreement.
7. **Synthesize** (Vivado for Artix-7 / Zynq, or Yosys + nextpnr for an ECP5): report Fmax, LUTs, FFs, **DSP48 usage** (one int8 MAC can pack 2 per DSP slice, a nice optimization), BRAM. Compute **peak GOPS = 2 · N² · Fmax** and achieved utilization.
8. Stretch: on a Zynq / PYNQ board, a Python notebook on the ARM core sends images to your accelerator via AXI DMA. A live "draw a digit" demo reuses your old project's UI!

Tools: same as `itch_fpga/` (Verilator/Icarus + **cocotb** + GTKWave/Surfer + Vivado/Yosys). Do the **Verilog ramp in itch_fpga/theory.md §2 first** (it's shared).

---

## 6. Interview questions
1. Why are DNN accelerators faster and more energy-efficient than CPUs/GPUs for inference?
2. Draw a systolic array for a 3×3 matmul and walk through the cycles. Why skew the inputs?
3. Weight- vs output- vs row-stationary: what does each minimize? Which suits batch-1 LLM decoding?
4. Explain the roofline model. Is LLM decoding compute- or memory-bound? Why? What helps? (Batching, quantization, KV-cache compression, speculative decoding.)
5. What's arithmetic intensity of GEMM vs GEMV?
6. How does int8 quantization work? Why int32 accumulators? What's requantization?
7. How do you map a convolution onto a matmul engine? Cost of im2col?
8. Your array is 128×128 and the layer is 1472 wide. What's the utilization? (1472 = 11.5 tiles of 128, so the last tile is half-empty and ~96% overall. Now explain your M2 GQA result.)
9. How would you implement softmax / GELU / LayerNorm in hardware?
10. What is double buffering and why does it matter?
11. How do you exploit sparsity? Why is unstructured sparsity hard in hardware?
12. FPGA specifics: what's a DSP slice? How many int8 MACs per DSP48E2? BRAM ports and widths?
13. (Design) Design an accelerator for a transformer's attention with a 4 MB on-chip SRAM budget. How do you tile? (→ FlashAttention-style tiling + online softmax.)

**AI-era probes:** "How did you know it computes the right thing?" (Bit-exact vs an integer NumPy golden model on 10k images.) "What limits your Fmax / utilization?" (Show the timing report and utilization math.) "How would a compiler target your hardware?" (→ `compiler/` option D.)

---

## 7. Resources (priority order)
1. **Sze, Chen, Yang, Emer, "Efficient Processing of Deep Neural Networks: A Tutorial and Survey"** (Proc. IEEE 2017, arXiv 1703.09039). Read §IV (hardware for DNN processing), §V (**dataflows: WS/OS/NLR/RS**, the clearest taxonomy) and §VII (reduced precision). Expanded into the book *Efficient Processing of Deep Neural Networks* (Morgan & Claypool, 2020): Ch. 3 (key metrics), Ch. 4 (kernel computation, im2col, tiling), Ch. 5 (dataflows), Ch. 7 (reduced precision).
2. **Jouppi et al., "In-Datacenter Performance Analysis of a Tensor Processing Unit" (ISCA 2017)**. TPU v1: read §2 (architecture, the **systolic MXU figure**) and the roofline section. ~1 hour.
3. **MIT 6.5930/1 "Hardware Architecture for Deep Learning" (Sze & Emer)**. Free lecture slides on the course website. Lectures on dataflows, the loop-nest notation and quantization. Pairs with #1.
4. **MIT 6.5940 "TinyML and Efficient Deep Learning Computing" (Song Han, YouTube + efficientml.ai)**. Lectures 5–6 (**quantization**). Lecture 3–4 (pruning/sparsity) is optional.
5. **Jacob et al., "Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only Inference" (CVPR 2018)**. §2 (quantization scheme) and §2.2 (**integer-only requantization with fixed-point multiplier**). This is exactly what your hardware's post-processing unit implements.
6. **Horace He, "Making Deep Learning Go Brrrr From First Principles"**. Compute/memory/overhead-bound framing. You'll enjoy it given your MFU work.
7. **Reference open-source designs (read, then build your own):**
   - `tiny-tpu-v2/tiny-tpu`: a minimal TPU re-imagined from TPU v1/v2 (systolic array + vector unit + an 88-bit ISA; a 2×2 matmul + ReLU design with docs). Good for option 5.
   - `deaneeth/tiny-tpu`: 4×4 **weight-stationary** int8 systolic array in SystemVerilog, **tested with cocotb** (MIT license). Closest to option 1.
   - `Alanma23/tinytinyTPU`: 2×2 array with Verilator + cocotb flow and a Basys3 deploy path via Yosys/nextpnr.
   - **Berkeley Gemmini (github.com/ucb-bar/gemmini)**: production-grade research generator. Read the README's architecture section for the scratchpad/accumulator/controller design.
8. **HDLBits + Cummings papers + cocotb docs** (same as itch_fpga §7) for the RTL skills.
9. **Kung, "Why Systolic Architectures?" (IEEE Computer, 1982)**. The original, short and very readable.
10. For option 4: **Milakov & Gimelshein, "Online normalizer calculation for softmax" (2018)** and the **FlashAttention** paper §3.1 (tiling + online softmax).
11. For option 7: **hls4ml docs + tutorial notebooks** (fastmachinelearning.org/hls4ml) and the AMD/Xilinx Vitis HLS user guide (pragma sections).
Communities: r/FPGA, r/computerarchitecture, r/hardware. The tiny-tpu projects have community Discords.

---

## 8. Metrics / resume line
> "Designed a parameterized N×N weight-stationary int8 systolic-array accelerator in SystemVerilog (+ tiling controller, double-buffered BRAM, fixed-point requantization). Runs a quantized MNIST MLP **bit-exact vs a PyTorch/NumPy golden model (97.x% acc.)**. **X GOPS peak at Y MHz** on Artix-7, using Z DSPs. Verified with cocotb."
