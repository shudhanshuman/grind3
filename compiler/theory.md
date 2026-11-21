# Your Own Compiler — Theory

> Goal: a compiler (or interpreter + compiler) for a small language, built end to end. Pick the flavour in §0. The theory in §1–6 is shared by all options.

---

## 0. Options (pick one when you start)

| Option | What you build | Language | Effort (v1) | Best for | Main resource |
|---|---|---|---|---|---|
| **A. Bytecode interpreter** for your own dynamic language | Lexer → Pratt parser → compile to bytecode → stack VM (+ closures, GC) | C | 3–4 weeks for the full clox | Learning everything gently. "VM/interpreter" story. | *Crafting Interpreters*, Part III |
| **B. C-subset → real assembly** (ARM64 on your M2, or x86-64) | Lexer → recursive-descent parser → AST → type check → (TACKY/IR) → assembly → `as`/`ld` → native binary | C, C++, Rust or Python | 2–4 weeks for ints, functions, pointers, arrays, structs | **"Real compiler" credibility.** Systems/compiler roles. | Nora Sandler, *Writing a C Compiler*; chibicc; acwj |
| **C. LLVM frontend** for a toy language | Lexer/parser/AST → emit **LLVM IR** → LLVM does the optimization and codegen → JIT or native | C++ | 1–2 weeks | Fast route to an optimizing compiler. LLVM on the resume. | LLVM *Kaleidoscope* tutorial |
| **D. ML / tensor compiler** (most aligned with your AI profile) | A tiny graph IR for tensor ops (from a PyTorch-like DSL or a traced micrograd/tinygrad model) → passes: shape inference, constant folding, **operator fusion**, **loop tiling** → codegen to C/Metal/NEON, *or to your neural accelerator's instruction stream* | Python (+ C codegen) | 2–3 weeks | ML-infra / AI-compiler roles (NVIDIA, Modular, AMD, Qualcomm, Google XLA, OpenAI Triton team). **Combines with the accelerator project.** | tinygrad source, MLIR Toy tutorial, Triton paper, TVM paper |

**My recommendation:** **B** if you want the classic, deep "I wrote a compiler that emits machine code" experience (fun, hard, and the theory transfers everywhere). **D** if you want it to compound with your AI/hardware story (compiler → your systolic array = a full-stack NPU project). You could do a small B-style frontend and reuse it in D later.

Mac note for B: Sandler's book targets **x86-64** (System V ABI). On an M2 you can assemble x86-64 and run it via **Rosetta 2** (`arch -x86_64`), or target **ARM64 (AArch64)** natively. Fewer instructions, more registers, a cleaner ABI, but you translate the book's codegen chapters yourself. Note: macOS prefixes C symbols with `_`.

---

## 1. Big picture: the pipeline

```
source text
  → LEXER (tokens)
  → PARSER (AST)
  → SEMANTIC ANALYSIS (name resolution, scopes, types)  → annotated AST
  → IR GENERATION (three-address code / SSA, control-flow graph)
  → OPTIMIZATION PASSES (on IR)
  → INSTRUCTION SELECTION → REGISTER ALLOCATION → INSTRUCTION SCHEDULING
  → assembly → assembler → linker → executable
```
Front end = language-specific. Back end = machine-specific. **IR** decouples them (that's LLVM's whole idea: N languages × M targets → N + M work).

Compiler vs interpreter vs JIT: compile ahead of time to machine code / walk the AST or bytecode at runtime / compile hot code at runtime (V8, PyPy, LuaJIT, the JVM).

---

## 2. Lexing (scanning)
- Turn characters into **tokens**: `KEYWORD(int)`, `IDENT(x)`, `INT_LIT(42)`, `PLUS`, `LPAREN`, …. Drop whitespace and comments, track line/column for error messages.
- Theory: tokens are **regular languages** → regular expressions → **NFA (Thompson's construction) → DFA (subset construction) → minimize**. Tools like flex automate this. Hand-written lexers are just a loop with a `switch` on the current char: **maximal munch** (`>=` beats `>` then `=`), keyword lookup after scanning an identifier.
- Interview: "Why can't regex parse nested parentheses?" (Regular languages can't count. You need a context-free grammar / pushdown automaton.)

## 3. Parsing
- **Context-free grammars (CFG)** in BNF/EBNF. Terminals, nonterminals, productions, derivations, parse trees vs **AST** (the AST drops the syntax noise).
- **Ambiguity:** `1 - 2 - 3` and `1 + 2 * 3` → fix with **precedence & associativity** layers in the grammar.
- **Top-down (LL):** **recursive descent**: one function per nonterminal. Needs no **left recursion** (rewrite `expr → expr + term` into a loop). LL(1) = decide with 1 lookahead token, using FIRST/FOLLOW sets.
- **Precedence climbing / Pratt parsing:** the elegant way to parse expressions. Each token has a binding power, and a loop handles infix operators. *Learn this.* It's 50 lines and handles all of precedence, associativity, prefix and postfix.
- **Bottom-up (LR, LALR, SLR):** shift-reduce with a parse table, used by yacc/bison. Know the concepts: shift/reduce and reduce/reduce **conflicts**, the dangling-else problem. You won't hand-write one.
- Real compilers (GCC, Clang, Go, Rust's rustc) use **hand-written recursive descent** for better error messages.
- Error recovery: **panic mode**, i.e. skip to a synchronizing token (`;`, `}`) and continue to report more errors.

## 4. Semantic analysis
- **Symbol tables & scopes:** a stack of hash maps. Lexical/static scoping, shadowing, name resolution, use-before-declare.
- **Type checking:** compute each expression's type bottom-up and check the rules (can't add a pointer to a pointer). Implicit conversions (C's "usual arithmetic conversions"), lvalues vs rvalues.
- **Type inference** (know it): Hindley–Milner / unification (ML, Haskell, Rust locally).
- Output: an AST annotated with types and resolved symbols (or "variable #7, stack offset −24").

## 5. Intermediate representation and optimization
- **Three-address code (TAC):** `t1 = a + b`, one operation per instruction, explicit temporaries. Sandler's book calls its IR "TACKY".
- **Basic blocks** (straight-line code, one entry, one exit) and the **control-flow graph (CFG)**.
- **SSA (Static Single Assignment):** every variable is assigned exactly once. **φ (phi) functions** merge values at join points. It makes most optimizations simple. Construct it via **dominators / dominance frontiers** (Cytron et al.). LLVM IR is SSA.
- **Dataflow analysis:** a framework (lattice + transfer function + fixpoint iteration). Instances: **liveness** (backward), **reaching definitions** (forward), available expressions.
- Classic optimizations (know what each does and give an example):
  | Pass | Example |
  |---|---|
  | Constant folding / propagation | `x = 2*3; y = x+1` → `y = 7` |
  | Dead code elimination | remove unused results, unreachable blocks |
  | Copy propagation | `y = x; z = y+1` → `z = x+1` |
  | Common subexpression elimination | compute `a*b` once |
  | Loop-invariant code motion | hoist `n*4` out of the loop |
  | Strength reduction | `i*4` in a loop → add 4 each iteration |
  | Inlining | replace a call with the body (enables everything else) |
  | Loop unrolling / vectorization | fewer branches, SIMD |
  | Tail-call optimization | recursion → loop |

## 6. Back end
- **Instruction selection:** map IR ops to machine instructions (tree pattern matching, or a simple 1:1 template expansion in a teaching compiler).
- **Register allocation:** finite registers. Values that don't fit are **spilled** to the stack.
  - **Graph coloring** (Chaitin/Briggs): build an **interference graph** (variables live at the same time can't share a register) → K-color it (NP-hard, so use heuristics) → spill when you can't. Plus coalescing to remove moves.
  - **Linear scan:** faster and simpler, used in JITs.
- **Calling conventions / ABI:** which registers hold args and the return value (x86-64 SysV: `rdi, rsi, rdx, rcx, r8, r9`, return in `rax`. AArch64: `x0–x7`, return in `x0`), caller- vs callee-saved registers, **stack frames** (frame pointer, return address, locals, alignment to 16 bytes).
- Then **assembler** (text → object file) and **linker** (resolve symbols, relocations, link libc). Know ELF/Mach-O basics: sections `.text`, `.data`, `.bss`, symbol table.
- Runtime topics for a dynamic language (option A): stack VM vs register VM, **garbage collection** (mark-sweep, copying, generational, reference counting + cycles), closures and upvalues, dynamic dispatch, NaN-boxing.

## 7. ML compiler extras (option D)
- **Computational graph IR:** nodes = tensor ops (matmul, add, relu, softmax), edges = tensors with shapes/dtypes.
- Passes: **shape inference**, constant folding, **operator fusion** (matmul + bias + relu → one kernel, which saves memory round trips; the #1 win, see Horace He's "brrr" post), layout transformation (NCHW ↔ NHWC), **quantization**.
- **Loop-level IR:** an op becomes a loop nest, then you **tile** for cache/SRAM, reorder, vectorize and parallelize. Halide's idea is **separating the algorithm from the schedule**, and TVM adopted it.
- **Polyhedral model** (know the name): loop nests as integer polyhedra for legal reordering.
- **MLIR:** multi-level IR with **dialects** (linalg, affine, scf, gpu…) progressively **lowered**. Triton = Python-level block programming → MLIR → PTX.
- Lowering to *your* accelerator: tile a matmul to the systolic array size (e.g. 8×8), schedule weight loads/activation streams, and emit an instruction stream. That's what Google's XLA does for TPUs, in miniature.

---

## 8. Interview questions
1. Walk through the phases of a compiler. What does each output?
2. Lexer vs parser: why separate? Why can't regex handle nested parens?
3. What's left recursion and why is it a problem for recursive descent? How do you remove it?
4. How do you handle operator precedence? (Grammar layering or Pratt parsing.)
5. AST vs parse tree.
6. What is SSA and why do compilers use it? What's a φ node?
7. Explain liveness analysis. How does it feed register allocation?
8. Register allocation as graph coloring: what happens when you run out of registers?
9. Name 5 optimizations and an example of each. Which are only valid under certain conditions? (E.g. reordering floating-point ops breaks associativity. Aliasing blocks reordering memory ops, which is why `restrict` exists.)
10. What's a calling convention? Caller- vs callee-saved?
11. Interpreter vs compiler vs JIT trade-offs. How does V8 or the JVM JIT work at a high level?
12. (C/C++ systems interviews) What does `volatile` do or not do? What is undefined behaviour and why do compilers exploit it?
13. (ML-compiler interviews) Why fuse operators? What's arithmetic intensity? How does TVM or Triton generate fast kernels? What's tiling?

**AI-era probe:** "LLMs can write code now. Why do compilers matter?" Good answer: every AI chip needs a compiler stack, and ML compilers (XLA, Triton, TVM, MLIR, Mojo/MAX, tinygrad) are among the hottest hiring areas. Plus: "How did you test your compiler?" Answer: a test suite of programs with expected outputs, run through your compiler vs `gcc`/`clang` (differential testing), and fuzzing with Csmith for C.

---

## 9. Resources (priority order)

**Core**
1. **Crafting Interpreters (Robert Nystrom, free at craftinginterpreters.com)**. The community's #1 beginner rec (r/ProgrammingLanguages, r/Compilers, HN). Read **Ch. 4 Scanning, Ch. 5 Representing Code, Ch. 6 Parsing Expressions** for any option. For option A, do all of **Part III (clox), Ch. 14–30**. Ch. 17 "Compiling Expressions" is the best Pratt parser explanation anywhere.
2. **Nora Sandler, *Writing a C Compiler* (No Starch Press, 2024)**. Option B. Part I (Ch. 1–10: return 2 → unary → binary → logical/relational → locals → if → compound statements → loops → functions → file scope) gives you a working compiler. Part II adds types (long, unsigned, double, pointers, arrays, structs). Part III is optimizations (constant folding, unreachable/dead-code elimination, copy propagation) + **register allocation (graph coloring)**. Test suite on GitHub (`nlsandler/writing-a-c-compiler-tests`). Free precursor: her blog series "Writing a C Compiler" (norasandler.com).
3. **chibicc (Rui Ueyama, github.com/rui314/chibicc)**. A small C11 compiler that self-hosts, built in **~300 tiny incremental commits**. Read the commit history in order. It's a tutorial in itself.
4. **acwj, "A Compiler Writing Journey" (DoctorWkt, GitHub)**. 60+ parts, from calculator to self-compiling C-subset compiler, with a write-up per step.
5. **LLVM "My First Language Frontend with LLVM" (Kaleidoscope) tutorial (llvm.org/docs/tutorial)**. Option C, Ch. 1–7.

**Theory depth (read selectively)**
6. **Cornell CS 6120 "Advanced Compilers", Adrian Sampson (free self-guided course online, with videos)**. Lessons on **IR/Bril, local optimization (DCE, LVN), dataflow, global analysis/dominators, SSA, LLVM**. Best free resource for the "middle end", and very practical.
7. **Cooper & Torczon, *Engineering a Compiler* (3rd ed.)**. Ch. 5 (IR), 8–9 (optimization, dataflow, SSA), 11 (instruction selection), 13 (register allocation). More readable than the Dragon Book.
8. **Aho, Lam, Sethi, Ullman, the "Dragon Book"**. Ch. 3 (lexing: NFA/DFA) and Ch. 4 (LL/LR parsing) are definitive. Use it as a reference only.
9. **Pratt parsing posts:** Bob Nystrom, "Pratt Parsers: Expression Parsing Made Easy"; Alex Kladov (matklad), "Simple but Powerful Pratt Parsing".

**ML compiler (option D)**
10. **tinygrad source (github.com/tinygrad/tinygrad)**: a real, small ML compiler (lazy graph → scheduler → kernel fusion → codegen to Metal/CUDA/C). It runs on your M2 via Metal.
11. **MLIR "Toy" tutorial (mlir.llvm.org/docs/Tutorials/Toy)**, Ch. 1–6: a language → dialect → shape inference → lowering to affine loops → LLVM.
12. **Horace He, "Making Deep Learning Go Brrrr From First Principles"** (blog). Compute- vs memory- vs overhead-bound, and why fusion matters.
13. Papers (skim the overviews): **TVM** (Chen et al., OSDI 2018), **Triton** (Tillet et al., MAPL 2019), **Halide** (Ragan-Kelley et al., PLDI 2013).

Communities: r/Compilers, r/ProgrammingLanguages (great sidebar resource list), the PLTD / r/ProgrammingLanguages Discord.

---

## 10. Metrics / resume line
- B: "Wrote a C-subset compiler in C++ (lexer, recursive-descent parser, type checker, TAC IR, constant folding/DCE/copy propagation, graph-coloring register allocation) emitting AArch64 assembly. Passes N/M tests of the *Writing a C Compiler* suite and compiles a K-line program."
- D: "Built a tensor compiler (graph IR, shape inference, op fusion, loop tiling) that lowers a PyTorch MLP to C/NEON (X× faster than unfused) and to my FPGA systolic array's ISA."
