# 🚀 CacheMind v0.1 Public Beta Evidence — Comprehensive Evaluation Report

**Document Version:** 1.0.0  
**Classification:** Scientific Benchmark & Empirical Performance Evaluation  
**Status:** Verified & Reproducible  
**Target Release:** CacheMind v0.1 Public Beta  

---

## 1. Executive Summary

**CacheMind** is an open-source, deterministic AI caching gateway and reverse proxy engineered to eliminate redundant LLM API expenditures, cut user-facing latency, and protect downstream inference from semantic cache poisoning.

This report documents the empirical evaluation of CacheMind v0.1 Public Beta across core operational pillars:
1. **Multi-Tier Latency & Throughput SLAs**: Client-observed p50 latency of **8.04 ms** (p95: 16.19 ms) on L1 exact hash hits ($c=1$) and **21.81 ms** (p95: 36.29 ms) on L2 quantized vector cache hits ($c=1$), measured against an in-process ASGI test harness.
2. **Single-Flight Request Coalescing**: 100% thundering herd / cache stampede prevention under concurrent bursts ($c \in \{10, 50, 100\}$), dispatching exactly 1 upstream API request while coalescing $N-1$ followers in memory.
3. **Semantic Safety & Anti-Poisoning**: Evaluation against 610 adversarial prompt pairs across 6 critical failure categories, demonstrating a **42.2 percentage-point decrease** in False Positive Rate (FPR) (a **~58.0% relative reduction**, from 72.80% down to 30.60%) and avoiding **211 unsafe semantic reuse decisions** compared to raw cosine similarity alone, with zero degradation to valid paraphrase recall (47.27%).
4. **FinOps & ROI Modeling**: Modeled net financial savings ranging from **$2,560.75/month** at 1M req/mo to **$135,387.50/month** at 50M req/mo (75.0% gross cost reduction) for GPT-4o after deducting transparent baseline gateway infrastructure overhead ($150/mo + $0.000008/req).
5. **Lifespan Startup Warmup**: Pre-warming ONNX inference graph and cache connections during startup, reducing first-request latency in a recorded benchmark run by **97.4%** (from 481.55 ms down to 12.38 ms).
6. **Kubernetes Health & Observability**: Sub-millisecond `/health/live` and deep async non-blocking `/health/ready` probe validation across database, cache, and embedding subsystems.

---

## 2. Test Environment & Scientific Reproducibility

All benchmarks and evaluations were executed in an isolated, reproducible test harness with automated environment capture.

### Hardware & Runtime Specification

| Parameter | Specification |
| :--- | :--- |
| **Operating System** | Windows 11 Pro (10.0.26200) / Linux (Ubuntu 22.04 LTS Compatible) |
| **Architecture** | x86_64 |
| **Python Runtime** | Python 3.14.6 (64-bit) |
| **Embedding Engine** | FastEmbed (`BAAI/bge-small-en-v1.5`, 384-dim, ONNX Runtime INT8) |
| **Vector Index** | pgvector / Qdrant / Local In-Memory Vector Index |
| **Cache Storage Backend** | Redis 7.2-compatible In-Memory LRU Engine |
| **Web Framework** | FastAPI 0.115+ / Starlette on AnyIO / Uvicorn |
| **HTTP Client Harness** | HTTPX 0.28+ (Async Connection Pooling & Keep-Alive, ASGI In-Process Transport) |

---

## 3. Empirical Gateway Latency & Throughput Benchmark Suite

Executed master benchmark runner `benchmarks/run_full_suite.py` against the full concurrency matrix ($c \in \{1, 10, 50, 100\}$), generating `benchmarks/results/gateway_benchmark_suite.json`. Each scenario executes **1,000 requests** per concurrency level.

### 3.1 Multi-Tier Latency & Throughput Matrix

| Scenario | Concurrency ($c$) | Throughput (RPS) | p50 Client Latency (ms) | p90 Client Latency (ms) | p95 Client Latency (ms) | p99 Client Latency (ms) | Mean Client Latency (ms) | Cache Hit Rate (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Exact Cache Hit (L1)** | 1 | **107.4** | **8.04** | 13.97 | 16.19 | 21.14 | 9.27 | **100.0%** |
| **Exact Cache Hit (L1)** | 10 | **134.9** | **67.26** | 117.84 | 136.08 | 157.69 | 73.66 | **100.0%** |
| **Exact Cache Hit (L1)** | 50 | **141.2** | **328.50** | 533.56 | 582.76 | 590.96 | 350.91 | **100.0%** |
| **Exact Cache Hit (L1)** | 100 | **133.0** | **630.94** | 1,056.88 | 1,154.98 | 1,179.40 | 698.92 | **100.0%** |
| **Semantic Cache Hit (L2)** | 1 | **46.1** | **21.81** | 30.65 | 36.29 | 58.20 | 21.67 | **66.6%** |
| **Semantic Cache Hit (L2)** | 10 | **66.6** | **144.81** | 177.30 | 194.92 | 221.02 | 148.86 | **66.6%** |
| **Semantic Cache Hit (L2)** | 50 | **67.5** | **710.07** | 907.41 | 966.60 | 1,082.43 | 732.19 | **66.6%** |
| **Semantic Cache Hit (L2)** | 100 | **71.2** | **1,355.22** | 1,604.22 | 1,689.24 | 1,777.55 | 1,367.43 | **66.6%** |
| **Cache Miss (35ms Upstream Delay)** | 1 | **12.0** | **79.50** | 100.99 | 108.15 | 122.04 | 83.04 | **0.0%** |
| **Cache Miss (35ms Upstream Delay)** | 10 | **177.1** | **51.81** | 64.93 | 70.27 | 242.24 | 56.12 | **0.0%** |
| **Cache Miss (35ms Upstream Delay)** | 50 | **192.7** | **237.18** | 345.92 | 379.10 | 391.02 | 252.02 | **0.0%** |
| **Cache Miss (35ms Upstream Delay)** | 100 | **172.2** | **531.50** | 798.81 | 889.70 | 904.91 | 547.47 | **0.0%** |
| **Mixed Workload (40/35/25)** | 1 | **23.3** | **16.68** | 93.42 | 110.21 | 134.25 | 42.66 | **75.3%** |
| **Mixed Workload (40/35/25)** | 10 | **41.7** | **222.77** | 373.13 | 465.80 | 589.25 | 238.35 | **100.0%**\* |
| **Mixed Workload (40/35/25)** | 50 | **43.0** | **1,156.04** | 1,461.72 | 1,615.94 | 1,834.30 | 1,152.37 | **100.0%**\* |
| **Mixed Workload (40/35/25)** | 100 | **45.4** | **2,084.85** | 2,721.99 | 2,738.39 | 2,899.49 | 2,186.43 | **100.0%**\* |
| **Customer Support 1k** | 10 | **19.9** | **467.12** | 802.40 | 865.07 | 1,003.00 | 500.80 | **82.7%** |
| **Customer Support 1k** | 50 | **25.2** | **2,160.53** | 2,762.75 | 2,970.98 | 3,491.10 | 1,953.34 | **100.0%**\* |
| **Customer Support 1k** | 100 | **29.4** | **3,514.87** | 4,870.72 | 5,425.01 | 5,559.35 | 3,267.75 | **100.0%**\* |

*\*Note on Hit Rates at Higher Concurrency:* In the benchmark runner harness, consecutive concurrency runs execute against a shared in-memory instance where cache entries populated during the initial concurrency sweep remain resident, resulting in warm-cache hit rates for subsequent runs.

---

## 4. Semantic Safety & Anti-Poisoning Evaluation

Evaluated across **610 adversarial prompt pairs** in `evaluation/semantic_safety/dataset.jsonl` with a full threshold sweep ($\tau \in [0.85, 0.98]$) recorded in `evaluation/semantic_safety/threshold_sweep.json` and `.csv`.

The dataset assesses 6 critical failure categories:
1. **Numerical Variance**: Queries with altered numeric quantities, pricing, or thresholds.
2. **Negation Inversion**: Queries with polarity flips ("enable" vs. "do not enable").
3. **Temporal Drift**: Queries referencing different dates, years, or quarters.
4. **Opposing Actions**: Queries specifying inverse operational intents ("increase" vs. "decrease").
5. **Entity Substitution**: Queries targeting distinct systems, tables, or tenants.
6. **Valid Semantic Paraphrases**: True positive linguistic variations that should be safely cached.

### 4.1 Comparative Defense Evaluation at Default Threshold ($\tau = 0.90$)

| Metric | Raw Cosine Similarity Alone | CacheMind Guardrail Arbiter | Defense Delta / Impact |
| :--- | :---: | :---: | :---: |
| **False Positive Rate (FPR)** | **72.80%** (364 / 500) | **30.60%** (153 / 500) | **-42.2 percentage points (~58.0% relative reduction)** |
| **Unsafe Semantic Reuse Decisions Avoided** | — | — | **211 unsafe decisions avoided** |
| **False Positives (Unsafe Cache Hits)** | 364 | 153 | **-211 cases** |
| **True Negatives (Safe Rejections)** | 136 | 347 | **+211 safe rejections** |
| **True Positives (Valid Hits Retained)** | 52 | 52 | **0.00% (Zero valid hit degradation)** |
| **Valid Paraphrase Recall** | **47.27%** (52 / 110) | **47.27%** (52 / 110) | **0.00% degradation** |
| **Precision** | 12.50% | 25.37% | **+12.87 percentage points** |
| **F1-Score** | 19.77% | 33.02% | **+13.25 percentage points** |
| **Overall Classification Accuracy** | 30.82% | 65.41% | **+34.59 percentage points** |

### 4.2 Cosine Similarity Threshold Sweep ($\tau = 0.85 \dots 0.98$)

| Threshold ($\tau$) | Raw FPR (%) | Guardrail FPR (%) | Raw Precision (%) | Guardrail Precision (%) | Paraphrase Recall (%) | Unsafe Decisions Avoided |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.85** | 94.00% | 42.40% | 13.76% | 26.13% | 68.18% | 258 cases |
| **0.86** | 90.60% | 40.60% | 14.20% | 26.98% | 68.18% | 250 cases |
| **0.87** | 87.80% | 38.60% | 14.59% | 27.99% | 68.18% | 246 cases |
| **0.88** | 84.40% | 37.40% | 13.35% | 25.79% | 59.09% | 235 cases |
| **0.89** | 80.20% | 33.80% | 13.02% | 26.20% | 54.55% | 232 cases |
| **0.90 (Default)** | **72.80%** | **30.60%** | **12.50%** | **25.37%** | **47.27%** | **211 cases** |
| **0.91** | 67.80% | 27.60% | 10.55% | 22.47% | 36.36% | 201 cases |
| **0.92** | 62.20% | 26.00% | 11.40% | 23.53% | 36.36% | 181 cases |
| **0.93** | 52.20% | 20.00% | 9.38% | 21.26% | 24.55% | 161 cases |
| **0.94** | 44.00% | 17.00% | 8.33% | 19.05% | 18.18% | 135 cases |
| **0.95** | 31.40% | 11.20% | 4.85% | 12.50% | 7.27% | 101 cases |
| **0.96** | 25.40% | 8.60% | 3.79% | 10.42% | 4.55% | 84 cases |
| **0.97** | 12.20% | 2.80% | 0.00% | 0.00% | 0.00% | 47 cases |
| **0.98** | 7.20% | 0.00% | 0.00% | 0.00% | 0.00% | 36 cases |

---

## 5. Single-Flight Request Coalescing Concurrency Proof

Measured single-flight request coalescing efficiency under concurrent traffic bursts on cold entries (`benchmarks/load/test_single_flight_coalescing.py`):

| Concurrency Level ($c$) | Total Requests | Upstream Leader Calls | Coalesced Followers | Upstream Calls Avoided (%) | Coalescing Efficiency |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **$c = 10$** | 10 | **1** | **9** | **90.0%** | **100.0%** |
| **$c = 50$** | 50 | **1** | **49** | **98.0%** | **100.0%** |
| **$c = 100$** | 100 | **1** | **99** | **99.0%** | **100.0%** |

---

## 6. FinOps Cost Avoidance vs. Net Realized Savings

Reconciled provider gross cost avoided against gateway compute overhead ($150/mo baseline instance + $0.000008 compute/request overhead) as modeled in `benchmarks/results/finops_report.json`:

$$\text{Gross Savings} = \text{Uncached Cost} - \text{Cached Provider Cost}$$
$$\text{Net Realized Savings} = \text{Gross Savings} - (\text{Baseline Base Infrastructure} + \text{Variable Compute Overhead})$$

### 6.1 GPT-4o Cost Projections (450 avg input tokens, 250 avg output tokens, 75.0% total hit rate)

| Monthly Request Volume | Uncached Spend (GPT-4o) | Cached Provider Spend | Gateway Infrastructure | Net Monthly Savings | Net ROI % |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **100,000 req/mo** | $362.50 | $90.62 | $150.80 | **$121.07** | 80.3% |
| **500,000 req/mo** | $1,812.50 | $453.12 | $154.00 | **$1,205.38** | 782.7% |
| **1,000,000 req/mo** | $3,625.00 | $906.25 | $158.00 | **$2,560.75** | **1,620.7%** |
| **5,000,000 req/mo** | $18,125.00 | $4,531.25 | $190.00 | **$13,403.75** | **7,054.6%** |
| **10,000,000 req/mo** | $36,250.00 | $9,062.50 | $230.00 | **$26,957.50** | **11,720.6%** |
| **50,000,000 req/mo** | $181,250.00 | $45,312.50 | $550.00 | **$135,387.50** | **24,615.9%** |

### 6.2 Claude 3.5 Sonnet Cost Projections

| Monthly Request Volume | Uncached Spend | Cached Provider Spend | Gateway Infrastructure | Net Monthly Savings | Net ROI % |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **100,000 req/mo** | $510.00 | $127.50 | $150.80 | **$231.70** | 153.6% |
| **1,000,000 req/mo** | $5,100.00 | $1,275.00 | $158.00 | **$3,667.00** | **2,320.9%** |
| **10,000,000 req/mo** | $51,000.00 | $12,750.00 | $230.00 | **$38,020.00** | **16,530.4%** |
| **50,000,000 req/mo** | $255,000.00 | $63,750.00 | $550.00 | **$190,700.00** | **34,672.7%** |

### 6.3 GPT-4o mini Cost Projections (Low-Cost Tier Model)

| Monthly Request Volume | Uncached Spend | Cached Provider Spend | Gateway Infrastructure | Net Monthly Savings | Net ROI % |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **100,000 req/mo** | $21.70 | $5.42 | $150.80 | **$0.00**\* | 0.0% |
| **1,000,000 req/mo** | $217.00 | $54.25 | $158.00 | **$4.75** | 3.0% |
| **10,000,000 req/mo** | $2,170.00 | $542.50 | $230.00 | **$1,397.50** | 607.6% |
| **50,000,000 req/mo** | $10,850.00 | $2,712.50 | $550.00 | **$7,587.50** | 1,379.6% |

*\*Note on Low-Cost Model Economics:* For highly inexpensive models such as GPT-4o mini, fixed gateway infrastructure costs exceed gross provider API savings at low request volumes (<1M req/mo). Break-even occurs above 1M req/mo.

---

## 7. Lifespan Startup Warmup & Cold-Start Analysis

- **Un-warmed Cold Start First Request (Recorded Observation):** `481.55 ms` (FastEmbed ONNX graph allocation + INT8 session optimization).
- **Post-Warmup Steady-State First User Request (Recorded Observation):** `12.38 ms`.
- **Recorded Cold-Start Reduction:** **97.4% reduction** via lifespan startup dry-run execution.
*(Note: Recorded from a single cold vs. pre-warmed execution run.)*

---

## 8. Kubernetes Health Probes & Operational Readiness

- **Liveness Probe (`GET /health/live`):** `200 OK`, latency `< 0.5 ms`, payload `{"status": "alive"}`.
- **Readiness Probe (`GET /health/ready`):** `200 OK`, latency `< 3.0 ms`, deep async non-blocking verification of SQLite/Postgres DB session (`SELECT 1`), Cache backend ping, and FastEmbed embedding engine initialization.

---

## 9. Workload Characteristics & Methodological Disclosures

To ensure scientific integrity and transparency, the following methodology constraints and disclosures apply:
1. **Synthetic Evaluation Datasets**: The semantic safety evaluation dataset (610 prompt pairs) and customer support dataset (1,000 queries) are synthetically constructed to systematically probe edge-case failure modes (numerical, negation, temporal, entity).
2. **Simulated Upstream Delay**: Cache miss benchmarks use a simulated 35ms upstream provider delay to isolate gateway routing, embedding, and caching overhead from variable public internet latencies.
3. **In-Memory Cache Retention Across Concurrency Runs**: In the automated benchmark suite runner, consecutive concurrency passes execute within a single runtime instance. Cache entries stored during initial runs remain warm in subsequent runs, resulting in observed 100% hit rates at higher concurrency levels.
4. **Single-Node In-Process Coalescing**: Single-flight request coalescing operates via in-memory `asyncio.Future` locks per gateway instance. Multi-node distributed coalescing requires shared Redis lock coordination.

---

## 10. Verification, Test Suite & Build Audits

1. **Backend Test Suite:** `pytest backend/tests -q` $\rightarrow$ **143 passed in 14.26s**.
2. **Next.js Dashboard Build:** `npm --prefix dashboard-app run build` $\rightarrow$ Compiled successfully across all 12 static/dynamic routes (`/`, `/analytics`, `/billing`, `/cache`, `/dashboard`, `/keys`, `/playground`, etc.).
3. **Secret Scan Audit:** All keys in test fixtures are dummy test prefixes (`cm_live_development_test_key_*`); zero live credentials in git history.

---

## 11. Threats to Validity & Known Limitations

1. **In-Process ASGI vs. Distributed Network Latency**: The benchmark harness utilizes HTTPX `ASGITransport` in-process communication. In production, network hop latency (0.5–2.0 ms in intra-datacenter environments) will add to total client-observed times.
2. **CPU ONNX Inference vs. GPU Acceleration**: FastEmbed embeddings run via ONNX Runtime on CPU (x86_64 INT8). GPU-accelerated embeddings or larger models (e.g., `text-embedding-3-small`) will exhibit different latency and throughput profiles.
3. **Threshold Sensitivity**: The 0.90 cosine similarity threshold represents a conservative baseline. Highly domain-specific workloads may require fine-tuning $\tau$ between 0.88 and 0.92 to optimize the precision-recall trade-off.

---

## 12. Independent Reproduction Guide

To independently reproduce all benchmarks, evaluations, and tests reported in this document:

```bash
# 1. Run Complete Unit & Integration Test Suite (143 tests)
python -m pytest backend/tests/ -q

# 2. Run Single-Flight Coalescing Concurrency Proof
python -m pytest backend/tests/integration/test_single_flight_coalescing_proof.py -v

# 3. Run Semantic Safety & Anti-Poisoning Evaluation Sweep
python evaluation/semantic_safety/evaluate.py --sweep

# 4. Run Full Master Gateway Benchmark Suite (1,000 requests each @ c=1, 10, 50, 100)
python benchmarks/run_full_suite.py

# 5. Execute FinOps Cost Modeling & ROI Projections
python benchmarks/finops/cost_model.py --model gpt-4o --exact-hit-rate 0.40 --semantic-hit-rate 0.35
```

---

*Report certified by CacheMind Core Engineering & Quality Assurance.*
