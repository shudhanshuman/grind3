# Vector Database — Theory

> Goal: a small but real vector database in C++ (or Rust): brute-force + **HNSW** + **IVF-PQ** indexes, a SIMD distance kernel, metadata filtering, persistence (WAL + snapshots / mmap), and a tiny HTTP/gRPC or Python API. It's benchmarked on SIFT1M / GloVe with recall-vs-QPS curves against FAISS / hnswlib.

Why it fits you: you've built LLMs and a RAG system (Vaani Board). This is the infrastructure underneath RAG. It reads well for ML-infra, backend and systems roles, and it's a natural system-design topic in AI-era interviews ("design semantic search for 1B documents").

---

## 1. Foundations

### Embeddings
- An encoder maps text/images to vectors in ℝᵈ (d = 384, 768, 1024, 1536, 3072…) so that semantic similarity ≈ geometric closeness. Examples: sentence-transformers, OpenAI/Cohere/Voyage embeddings, CLIP for images.
- **Matryoshka embeddings:** the first k dims are themselves a usable embedding, so you can truncate to trade accuracy for memory.
- A vector DB stores (id, vector, metadata) and answers: *given query q, return the k ids with the smallest distance.*

### Distance metrics
| Metric | Formula | Notes |
|---|---|---|
| L2 (Euclidean) | ‖x − q‖² | Skip the sqrt for ranking |
| Inner product (IP) | −x·q | "MIPS". Not a true metric (no triangle inequality). |
| Cosine | 1 − x·q/(‖x‖‖q‖) | **Normalize at insert → cosine == IP.** Do this. |
| Hamming | popcount(x XOR q) | For binary-quantized vectors |
Identity worth knowing: ‖x−q‖² = ‖x‖² + ‖q‖² − 2x·q. So batched L2 search = a **matrix multiply** (GEMM) + norms, which is how FAISS does brute force on GPUs.

### Exact kNN (brute force, "Flat" index)
- O(N·d) per query. With SIMD (NEON on your M2, AVX2/AVX-512 on x86) and a **top-k heap** (max-heap of size k), 1M × 128-d is ~tens of ms per query on one core.
- **Always build Flat first.** It's your ground truth for recall.

### The curse of dimensionality
- In high d, distances concentrate (nearest and farthest neighbours become nearly equidistant), and space-partitioning trees (KD-tree, ball tree) degrade to brute force beyond ~20 dims.
- So we use **approximate** NN (ANN): trade a bit of recall for orders-of-magnitude speed.

### Metrics for ANN
- **Recall@k** = |ANN top-k ∩ exact top-k| / k. **QPS** (queries/sec), **latency p50/p99**, **build time**, **memory per vector**, **update/delete support**.
- The standard visualization is a **recall-vs-QPS Pareto curve** while sweeping a search parameter (efSearch, nprobe). This plot is your project's money shot.

---

## 2. ANN index families

### 2.1 Hashing: LSH (know it, don't build it)
Random hyperplanes (SimHash) map similar vectors to the same bucket with high probability. Simple and theoretically clean, but it needs many tables for good recall. Mostly obsolete for dense embeddings and mostly appears as an interview question.

### 2.2 Clustering: IVF (Inverted File index)
1. Train **k-means** on a sample to get `nlist` centroids (e.g. √N to 4√N).
2. Each vector goes into the list ("posting list") of its nearest centroid.
3. Query: find the `nprobe` nearest centroids, then scan only those lists.
- Knobs: `nlist` (more = smaller lists, but more centroid comparisons), `nprobe` (more = higher recall, slower).
- Failure mode: a query near a cluster boundary has true neighbours in an unprobed list, which is why nprobe > 1.

### 2.3 Quantization: compressing vectors
- **Scalar quantization (SQ8):** float32 → int8 per dimension (min/max per dim). 4× smaller, small recall loss. Same idea as LLM int8 quantization, which you know.
- **Binary quantization:** sign bit per dim → 32× smaller, Hamming distance via popcount. Use it for a fast first pass, then **rerank** with full vectors.
- **Product Quantization (PQ)** (*read this paper*):
  - Split d dims into **m subspaces** (e.g. 128-d → m=16 × 8-d).
  - Run k-means in each subspace with **256 centroids** → each sub-vector becomes a 1-byte code. A 128-d float vector (512 B) → **16 bytes**.
  - **ADC (asymmetric distance computation):** for a query, precompute a table `T[m][256]` of distances from each query sub-vector to every sub-centroid. Distance to any database vector = **m table lookups + adds**. That's the trick that makes PQ fast.
  - **IVF-PQ:** IVF for coarse partitioning + PQ-encode the **residual** (vector − centroid). The workhorse of billion-scale search.
  - OPQ: learn a rotation first so subspaces are balanced. Know it exists.
  - Modern twist: **fast-scan PQ** with 4-bit codes and SIMD shuffle lookups (FAISS `PQFastScan`, Google ScaNN's anisotropic quantization).

### 2.4 Graphs: HNSW (**the main thing to build**)
- **Navigable small world (NSW):** each vector is a node connected to ~M near neighbours. Search = **greedy best-first walk** from an entry point toward the query, keeping a candidate priority queue of size `ef`.
- **Hierarchical NSW:** like a **skip list** over graphs. Each node gets a random max level `l = floor(−ln(U) · mL)` with `mL = 1/ln(M)`. Upper layers are sparse "highways", layer 0 has everything.
- **Search:** start at the top-layer entry point, greedy-descend with ef=1 to layer 1, then at layer 0 run the beam search with `ef = efSearch`, and return the top k.
- **Insert:** pick the level, search down to find `efConstruction` candidates per layer, connect to M of them using the **neighbour-selection heuristic** (keep a candidate only if it's closer to the new node than to any already-selected neighbour, which spreads edges in diverse directions), add reverse edges, and prune neighbours exceeding `M_max` (layer 0 uses `2M`).
- Knobs: `M` (graph degree, 16–64), `efConstruction` (100–500, build quality), `efSearch` (query-time recall/speed dial).
- **Deletes are hard:** use tombstones + skip at search time + periodic rebuild, or repair the neighbourhoods.
- Pros: best recall/QPS in RAM. Cons: memory-hungry (vectors + edges ≈ (d·4 + M·2·4) B per vector), slow-ish build, random access patterns (bad for disk).

### 2.5 Disk-based graphs: DiskANN / Vamana (know it)
Single-layer graph built with **α-pruning** (α > 1 keeps longer edges), PQ codes in RAM for navigation, full vectors + adjacency on SSD, and a few SSD reads per hop. Billion-scale on one machine. Know the idea for system-design questions.

### Which index when (interview gold)
| Situation | Pick |
|---|---|
| < 100k vectors | Flat (brute force). Don't overthink it. |
| Fits in RAM, need high recall, low latency | HNSW |
| Huge (100M–1B+), memory-constrained | IVF-PQ (+ rerank) |
| Billions, SSD available | DiskANN |
| Heavy filtering by metadata | Filter-aware HNSW / partition by tenant / pre-filter + brute force if selective |
| GPU available, batch queries | GPU Flat or IVF (FAISS GPU, CAGRA) |

---

## 3. The "database" part (what separates it from just an index)

| Feature | Concept |
|---|---|
| **Persistence** | Write-ahead log (WAL): append every insert/delete, fsync, replay on crash. Periodic **snapshots** of the index. **mmap** the vector file so the OS pages it in. |
| **Segments** | LSM-like: new inserts go to a small mutable segment (Flat or small HNSW). Seal it when full, build a bigger index in the background, **merge/compact** segments and drop tombstones. This is how Milvus, Weaviate, Lucene and Qdrant work. |
| **Metadata filtering** | *Pre-filter* (filter first → exact search on survivors, good when very selective), *post-filter* (ANN then drop, which can return < k results), *in-filter* (skip non-matching nodes during HNSW traversal but still traverse them; graph connectivity breaks under very selective filters). Know all three and their failure modes. |
| **Hybrid search** | Combine BM25 (keyword, inverted index) + vector results with **Reciprocal Rank Fusion**: score = Σ 1/(60 + rank). Common in production RAG. |
| **Concurrency** | Many readers + one writer. Per-node locks in HNSW (hnswlib does this), or RCU/copy-on-write segments. |
| **Distributed (design-level only)** | Shard by id hash, query all shards (scatter-gather), merge top-k. Replicate for availability. |
| **API** | `create_collection(dim, metric)`, `upsert(id, vec, meta)`, `delete(id)`, `search(q, k, filter, ef)`. Expose over HTTP (cpp-httplib / crow) or Python bindings (pybind11 / nanobind). |

---

## 4. Performance engineering (where you'll learn the most)
- **SIMD distance kernels:** write L2/IP with NEON intrinsics (`vfmaq_f32`) on your M2, and compare against the auto-vectorized scalar loop. Look at the assembly (godbolt.org).
- **Memory layout:** store vectors in one contiguous aligned array (SoA), not `vector<vector<float>>`. Store HNSW layer-0 adjacency in a flat fixed-size array per node (hnswlib's trick: vector + neighbours in one block, so one cache miss fetches both).
- **Prefetching** (`__builtin_prefetch`) neighbours' vectors before computing distances during traversal.
- **Visited set:** a reusable `vector<uint16_t>` with a generation counter instead of clearing a bitset per query.
- **Batching + multithreading** for build and for batched queries.
- Your LLaMA MFU work transfers directly: flat search is memory-bandwidth-bound. Compute the roofline. Bytes/query = N·d·4.

---

## 5. Build plan
1. Data loader for **SIFT1M** (fvecs/ivecs format) and **GloVe-100-angular** from ann-benchmarks. Ground-truth neighbours come with the dataset.
2. Flat index + SIMD + top-k heap → verify recall = 1.0.
3. HNSW (insert + search + heuristic) → recall/QPS curve vs **hnswlib** on the same data.
4. IVF (with your own k-means) → IVF-PQ with ADC lookup tables → compare against FAISS `IndexIVFPQ`.
5. Persistence: WAL + snapshot + crash test (kill -9 mid-insert, then recover).
6. Filtering + Python bindings + a demo: semantic search over arXiv abstracts or your own notes, embedded with a small sentence-transformer. A RAG demo using your own DB is a great README GIF.

---

## 6. Interview questions

**Concept**
1. Why does a KD-tree fail for 768-d vectors?
2. Cosine vs dot vs L2: when are they equivalent? Why normalize?
3. Explain HNSW. Why the hierarchy? What do M, efConstruction and efSearch do? Time/space complexity (search ≈ O(log N) empirically)?
4. Explain PQ. How many bytes per vector? Why is ADC fast? What's the recall cost?
5. IVF: what happens with nprobe=1 for a query near a centroid boundary?
6. How do you handle deletes in HNSW?
7. Pre- vs post- vs in-filtering. What breaks with a filter matching 0.1% of data?
8. How do you evaluate an ANN index? Draw the recall-QPS curve.

**System design (very common now)**
9. Design a RAG system for 10M company documents: chunking, embedding model choice, index choice, metadata/ACL filtering, hybrid search, reranking (cross-encoder), freshness/updates, evaluation (recall@k on a labelled set, answer faithfulness).
10. Scale to 1B vectors on a budget: IVF-PQ or DiskANN, sharding, memory math (1B × 768 × 4 B = 3 TB raw → PQ 64 B = 64 GB).
11. Embeddings were updated to a new model. How do you migrate? (Re-embed everything, dual-write, A/B, since vectors from different models aren't comparable.)
12. Do you even need a vector DB? (pgvector / a FAISS file / brute force for small N. Interviewers like this nuance.)

**AI-era probes**
- "Show your recall-QPS curve vs hnswlib. Why is yours slower?" (Memory layout, prefetching, visited-set cost.)
- "How did you check your HNSW is correct?" (Recall vs Flat ground truth. Graph connectivity check: every node reachable from the entry point.)

---

## 7. Resources (priority order)
1. **Pinecone Learn, "Faiss: The Missing Manual"** (pinecone.io/learn/series/faiss). Chapters: *Introduction to Similarity Search*, *Nearest Neighbor Indexes for Similarity Search* (Flat/LSH/HNSW/IVF overview), *Product Quantization*, *HNSW*, *Composite Indexes / IVF-PQ*. Best intuitive explanations with diagrams. Read these first (~4 h).
2. **HNSW paper: Malkov & Yashunin, "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs"** (arXiv 1603.09320). Read §4 and **Algorithms 1–5** (INSERT, SEARCH-LAYER, SELECT-NEIGHBORS-SIMPLE / HEURISTIC, K-NN-SEARCH). You implement directly from the pseudocode.
3. **PQ paper: Jégou, Douze, Schmid, "Product Quantization for Nearest Neighbor Search"** (IEEE TPAMI 2011). §II–IV (PQ, ADC vs SDC, IVFADC).
4. **hnswlib source (github.com/nmslib/hnswlib), `hnswalg.h`**: ~1,000 lines, the cleanest production HNSW. Read it *after* your first version to see the memory layout tricks.
5. **FAISS wiki (github.com/facebookresearch/faiss/wiki)**: "Getting started", "Faiss indexes", "Guidelines to choose an index", "Indexing 1M vectors". Plus the 2024 paper "The Faiss library" (arXiv 2401.08281) for the design rationale.
6. **antirez (Redis creator), blog post on implementing HNSW from scratch in C for Redis Vector Sets** (antirez.com/news/156). Practical engineering decisions (deletes, quantization, memory) from someone who did exactly this project.
7. **"What's the story with HNSW?"** (Towards Data Science) and **"Building an HNSW Index From Scratch in C++"** (Towards AI). Two complementary walkthroughs if the paper feels dense.
8. **ann-benchmarks.com + github.com/erikbern/ann-benchmarks**: datasets (SIFT, GloVe, GIST) with ground truth, and reference recall/QPS plots to compare against.
9. **DiskANN paper: Subramanya et al., NeurIPS 2019** (§2–3, Vamana). Read only for system-design depth.
10. **CMU 15-445 Database Systems (Andy Pavlo, YouTube)**: the lectures on *Buffer Pools*, *Storage* and *Logging/Recovery* for the persistence part. Optional.
11. Free Maven live-coding session *"Build a vector database from scratch"* (Doug Turnbull & John Berryman) if you prefer watching someone build.

---

## 8. Metrics / resume line
> "C++ vector database (HNSW + IVF-PQ, NEON-SIMD kernels, WAL persistence, filtered search, Python bindings). On SIFT1M: **recall@10 = 0.95 at X k QPS** (within Y% of hnswlib). IVF-PQ compresses 512 B → 16 B/vector at recall@10 = Z."
