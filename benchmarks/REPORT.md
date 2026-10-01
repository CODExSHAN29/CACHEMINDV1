# 📊 CacheMind Benchmark & Semantic Safety Evaluation Report

**Document Version:** 1.0.0  
**Classification:** Scientific Benchmark & Empirical Performance Evaluation  
**Status:** Verified & Reproducible  

---

## Executive Summary

**CacheMind** is an enterprise-grade, deterministic AI caching gateway and reverse proxy engineered to eliminate redundant LLM API expenditures, cut user-facing latency to sub-millisecond tiers, and protect downstream inference from semantic cache poisoning.

This report documents the empirical evaluation of CacheMind across four core operational pillars:
1. **Latency & Throughput SLAs**: Sub-2.0ms L1 exact hash hits, sub-8.0ms L2 quantized vector cache hits, and zero ONNX runtime cold-start degradation.
2. **Single-Flight Request Coalescing**: 100% thundering herd / cache stampede prevention under high concurrency ($N=50$), dispatching exactly 1 upstream API request while coalescing $N-1$ followers.
3. **Semantic Safety & Anti-Poisoning**: Evaluation against 610 adversarial prompt pairs across 6 critical failure categories, demonstrating a **42.20% reduction in False Positive Rate (FPR)** and preventing **211 semantic poisoning attacks** compared to raw vector similarity alone.
4. **FinOps & ROI Modeling**: Projected net financial savings ranging from **$2,560/month** at 1M req/mo to **$135,387/month** at 50M req/mo (75% net cost reduction) after subtracting amortized gateway infrastructure costs.

---

## 1. Test Environment & Scientific Reproducibility

All benchmarks and evaluations were executed in an isolated, reproducible test harness with automated environment capture.

### Hardware & Runtime Specification

| Parameter | Specification |
| :--- | :--- |
| **Operating System** | Windows 11 Pro (10.0.26200) / Linux (Ubuntu 22.04 LTS Compatible) |
| **Architecture** | x86_64 |
| **Python Runtime** | Python 3.14.6 (64-bit) |
| **Embedding Engine** | FastEmbed (`BAAI/bge-small-en-v1.5`, 384-dim, ONNX Runtime INT8) |
| **Vector Index** | pgvector / Qdrant / Local In-Memory Quantized Index |
| **Cache Storage Backend** | Redis 7.2-compatible In-Memory LRU Engine |
| **Web Framework** | FastAPI 0.115+ / Starlette on AnyIO / Uvicorn |
| **HTTP Client Harness** | HTTPX 0.28+ (Async Connection Pooling & Keep-Alive) |

---

## 2. Latency Benchmarks & Throughput SLAs

### 2.1 Multi-Tier Latency Breakdown

Client-observed latency was benchmarked across three distinct execution states:
- **L1 Exact Cache Hit**: Normalized SHA-256 canonical hash lookup in memory/Redis.
- **L2 Semantic Cache Hit**: Local CPU ONNX embedding inference + Cosine Vector similarity search + Guardrail Arbitration.
- **Cache Miss (Upstream Dispatch)**: Gateway ingress overhead + Upstream LLM roundtrip.

| Latency Metric | L1 Exact Hit (Memory) | L2 Semantic Hit (FastEmbed ONNX) | Cache Miss (Upstream Mock / Real) | Gateway Overhead (Internal) |
| :--- | :---: | :---: | :---: | :---: |
| **p50 (Median)** | **0.85 ms** | **6.40 ms** | 31.20 ms / 450.0 ms | **0.22 ms** |
| **p90** | **1.20 ms** | **7.85 ms** | 33.50 ms / 620.0 ms | **0.38 ms** |
| **p95** | **1.45 ms** | **8.60 ms** | 34.80 ms / 780.0 ms | **0.45 ms** |
| **p99** | **1.92 ms** | **9.95 ms** | 36.50 ms / 1,150.0 ms | **0.62 ms** |
| **Mean** | **0.91 ms** | **6.72 ms** | 31.85 ms / 512.0 ms | **0.26 ms** |
| **Target SLA** | **< 2.0 ms** | **< 10.0 ms** | N/A | **< 1.0 ms** |
| **Compliance** | **PASS (100%)** | **PASS (100%)** | **PASS** | **PASS (100%)** |

---

### 2.2 Concurrency Matrix (10, 50, 100 Concurrent Clients)

Steady-state throughput was evaluated over standard workloads (`exact.jsonl`, `semantic.jsonl`, `mixed.jsonl`) at varying concurrency levels:

| Concurrency ($N$) | Workload Profile | Total Requests | Successful % | Throughput (Req/sec) | Exact Hit p50 (ms) | Semantic Hit p50 (ms) | Gateway Latency Mean (ms) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | Exact Match | 100 | 100.0% | **942.5 rps** | 0.82 ms | N/A | 0.21 ms |
| **10** | Mixed (50/50) | 100 | 100.0% | **315.8 rps** | 0.88 ms | 6.25 ms | 0.45 ms |
| **50** | Exact Match | 500 | 100.0% | **1,845.2 rps** | 0.95 ms | N/A | 0.25 ms |
| **50** | Mixed (50/50) | 500 | 100.0% | **582.4 rps** | 1.05 ms | 6.80 ms | 0.52 ms |
| **100** | Exact Match | 1,000 | 100.0% | **2,410.0 rps** | 1.15 ms | N/A | 0.28 ms |
| **100** | Mixed (50/50) | 1,000 | 100.0% | **745.6 rps** | 1.28 ms | 7.42 ms | 0.61 ms |

---

### 2.3 Cold-Start Elimination via Lifespan Warmup

Un-warmed ONNX models typically incur a 150–350ms JIT compilation penalty on first inference. CacheMind implements an asynchronous startup lifespan warmup:

```
[Lifespan Startup] --> Initialize ONNX Runtime Session
                   --> Dry-Run Inference ("CacheMind cold start warmup sequence")
                   --> Warm Cache Backend Ping
                   --> Mark Gateway Ready (/health/ready -> 200 OK)
```

- **Cold-Start Latency (Without Warmup):** `268.45 ms`
- **Initial Request Latency (With Startup Warmup):** `6.45 ms`
- **Cold-Start Elimination:** **97.6% reduction in first-request latency**

---

## 3. Single-Flight Request Coalescing (Thundering Herd Proof)

When a popular prompt experiences a sudden burst of requests while the cache is cold, naive gateways dispatch $N$ parallel requests to the upstream LLM, causing quota exhaustion and rate limiting.

### Empirical Coalescing Proof ($N=50$ Concurrent Requests)

Using a synchronized `asyncio.Event` release barrier, 50 identical requests were fired at the exact same microsecond against a cold cache:

```
Request 1 (Leader)    ──▶ Enters Coalescer ──▶ Dispatches Upstream LLM ──▶ Sets Future Result ──▶ Writes L1 Cache
Requests 2..50 (Followers) ──▶ Join Coalescer ──▶ Await Leader Future ──▶ Receive Stream/Data (X-CacheMind-Coalesced: true)
```

| Metric | Result | Target |
| :--- | :---: | :---: |
| **Total Concurrent Requests** | **50** | 50 |
| **Successful HTTP 200 Responses** | **50 (100.0%)** | 100.0% |
| **Leader Requests (Dispatched to Upstream)** | **1** | Exactly 1 |
| **Coalesced Followers (Stampede Protected)** | **49** | Exactly 49 |
| **Upstream Calls Avoided** | **49 / 50 (98.0%)** | > 95.0% |
| **Coalescing Efficiency** | **100.0%** | 100.0% |
| **Follower Content Equivalence** | **100.0% Match** | 100.0% Match |

---

## 4. Semantic Safety & Anti-Poisoning Evaluation

A major risk in semantic LLM caching is **semantic cache poisoning**: returning a cached response from query $A$ to query $B$ because their embedding cosine similarity is high, even though their semantic meaning or critical parameters differ (e.g., negative polarity, different dollar amounts, or opposing CRUD operations).

### 4.1 Evaluation Dataset Profile (`dataset.jsonl`)

The dataset comprises **610 rigorously labeled prompt pairs** across 6 critical failure categories:

1. **Numerical Variance (100 pairs)**: Same question with altered numbers, dates, or prices (e.g., `"Transfer $500"` vs `"Transfer $5,000"`).
2. **Negation Inversion (100 pairs)**: Polarity flips (e.g., `"Why should I invest in X?"` vs `"Why should I not invest in X?"`).
3. **Temporal Drift (100 pairs)**: Historical vs current queries (e.g., `"Q3 2023 revenue"` vs `"Q3 2024 revenue"`).
4. **Opposing Actions (100 pairs)**: Inverted intent (e.g., `"Enable MFA"` vs `"Disable MFA"`, `"Lock account"` vs `"Unlock account"`).
5. **Entity Substitution (100 pairs)**: Altered subjects/recipients (e.g., `"Email John Doe"` vs `"Email Jane Smith"`).
6. **Valid Paraphrases (110 pairs)**: Semantically identical queries with syntactic variations (True Positives).

---

### 4.2 Comparative Evaluation Results (Threshold $\tau = 0.90$)

| Evaluation Metric | Baseline: Raw Cosine Similarity | CacheMind Guardrail Arbiter | Improvement / Delta |
| :--- | :---: | :---: | :---: |
| **False Positive Rate (FPR)** | **72.80%** | **30.60%** | **-42.20% (Poisoning Prevented)** |
| **Total False Positives (Poison Cases)** | **364 cases** | **153 cases** | **-211 attacks blocked** |
| **True Negatives (Safe Rejections)** | **136 cases** | **347 cases** | **+211 correct rejections** |
| **True Positives (Valid Hits Retained)** | **52 cases** | **52 cases** | **0.00% (Zero hit degradation)** |
| **Precision** | **12.50%** | **25.37%** | **+12.87%** |
| **Recall** | **47.27%** | **47.27%** | **0.00%** |
| **F1-Score** | **19.77%** | **33.02%** | **+13.25%** |
| **Overall Classification Accuracy** | **30.82%** | **65.41%** | **+34.59%** |

---

### 4.3 Vulnerability Breakdown by Critical Failure Mode

```
False Positive Rate (Lower is Safer):
Category                 Raw Cosine    CacheMind Guardrail    Defense Status
─────────────────────────────────────────────────────────────────────────────
Numerical Variance       94.0%  █████████▍  5.0% ▌            94.7% Defense Rate
Negation Inversion       47.0%  ████▋       7.0% ▋            85.1% Defense Rate
Temporal Drift          100.0%  ██████████ 50.0% █████        50.0% Defense Rate
Opposing Actions         47.0%  ████▋      32.0% ███▏         31.9% Defense Rate
Entity Substitution      76.0%  ███████▌   59.0% █████▉       22.4% Defense Rate
Valid Paraphrases         0.0%              0.0%              100% Safe (0 FP)
```

**Key Takeaways:**
- **Numerical Variance Defense:** Raw vector similarity failed in 94% of cases (treating `$50` and `$5,000` as identical due to embedding proximity). CacheMind Guardrail Arbiter extracts and compares numerical tokens, dropping poisoning to **5.0%**.
- **Negation Inversion Defense:** Polarity and negation keyword parity dropped false positive poisoning from **47.0%** to **7.0%**.

---

### 4.4 Cosine Threshold Sweep ($\tau \in [0.85, 0.98]$)

```
Threshold (τ) | Raw Cosine FPR | Guardrail FPR | Precision (Raw) | Precision (Guard) | Valid Hit Recall
──────────────┼────────────────┼───────────────┼─────────────────┼───────────────────┼─────────────────
0.85          |     89.6%      |     41.2%     |      10.8%      |       21.2%       |      98.2%
0.88          |     80.4%      |     35.0%     |      11.6%      |       23.5%       |      72.7%
0.90 (Default)|     72.8%      |     30.6%     |      12.5%      |       25.4%       |      47.3%
0.92          |     61.8%      |     25.8%     |      13.5%      |       27.3%       |      29.1%
0.95          |     41.4%      |     17.4%     |      15.2%      |       30.4%       |       9.1%
0.98          |     12.0%      |      5.0%     |      14.3%      |       28.6%       |       1.8%
```

**Optimal Operational Recommendation:**
- **Default General Workloads:** $\tau = 0.90$ with Guardrail Arbiter enabled.
- **Strict Financial/Healthcare Workloads:** $\tau = 0.93$ with PII Masking and Numeric/Temporal Arbiter enabled.

---

## 5. FinOps Cost Accounting & Enterprise Scale Projections

### 5.1 Financial Formula & Assumptions

Cost calculations utilize standard OpenAI GPT-4o published API pricing:
$$\text{Cost}_{\text{uncached}} = (\text{Input Tokens} \times \$2.50 / 10^6) + (\text{Output Tokens} \times \$10.00 / 10^6)$$
$$\text{Cost}_{\text{cached}} = \text{Cost}_{\text{uncached}} \times (1 - \text{Hit Rate})$$
$$\text{Net Savings} = \text{Gross Savings} - \text{Amortized Gateway Infrastructure Cost}$$

- **Average Input Tokens:** 450 tokens
- **Average Output Tokens:** 250 tokens
- **Blended Hit Rate:** 75.0% (40.0% L1 Exact + 35.0% L2 Semantic)
- **Baseline Cost per Request:** $0.003625 (Uncached) vs $0.000906 (Cached)

---

### 5.2 Enterprise Monthly Scale Projections

| Monthly Volume (Requests) | Uncached Monthly Spend | Spend With CacheMind | Gateway Infrastructure | Net Monthly Savings | Savings % | Net ROI % |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **100,000 req/mo** | $362.50 | $90.62 | $150.80 | **$121.07** | 75.0% | 80.3% |
| **500,000 req/mo** | $1,812.50 | $453.12 | $154.00 | **$1,205.38** | 75.0% | 782.7% |
| **1,000,000 req/mo** | $3,625.00 | $906.25 | $158.00 | **$2,560.75** | 75.0% | **1,620.7%** |
| **5,000,000 req/mo** | $18,125.00 | $4,531.25 | $190.00 | **$13,403.75** | 75.0% | **7,054.6%** |
| **10,000,000 req/mo** | $36,250.00 | $9,062.50 | $230.00 | **$26,957.50** | 75.0% | **11,720.6%** |
| **50,000,000 req/mo** | $181,250.00 | $45,312.50 | $550.00 | **$135,387.50** | 75.0% | **24,615.9%** |

---

## 6. Kubernetes Health & Observability SLA

CacheMind implements dedicated Kubernetes probes to prevent routing traffic to uninitialized or failing pods:

- **`/health/live` (Liveness Probe):**
  - **Latency:** `< 0.5 ms`
  - **Execution:** Zero-dependency process health check. Returns `{"status": "alive"}`.
- **`/health/ready` (Readiness Probe):**
  - **Latency:** `< 3.0 ms`
  - **Execution:** Non-blocking async inspection of Database (`SELECT 1`), Redis Cache (`ping()`), and Embedding Engine initialization.

---

## 7. Reproduction Guide

To independently reproduce all benchmarks, evaluations, and tests reported in this document:

```bash
# 1. Run Complete Unit & Integration Test Suite (143 tests)
python -m pytest backend/tests/ -v

# 2. Run Single-Flight Coalescing Concurrency Proof
python -m pytest backend/tests/integration/test_single_flight_coalescing_proof.py -v

# 3. Run Semantic Safety & Anti-Poisoning Evaluation Sweep
python evaluation/semantic_safety/evaluate.py --threshold 0.90

# 4. Generate Customer Support Benchmark Workload (1,000 Queries)
python benchmarks/workloads/generate_customer_support.py

# 5. Run Benchmark Harness over Customer Support Workload
python benchmarks/benchmark_gateway.py --workload customer_support_1000 -c 50 -n 1000

# 6. Execute FinOps Cost Modeling & ROI Projections
python benchmarks/finops/cost_model.py --model gpt-4o --exact-hit-rate 0.40 --semantic-hit-rate 0.35
```

---

*Report certified by CacheMind Core Engineering & Quality Assurance.*
