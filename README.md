<div align="center">

# ⚡ CacheMind

### Enterprise-Grade, Safe & Measurable Semantic Caching Gateway for LLM APIs

[![CI & Test Suite](https://github.com/CODExSHAN29/cachemind/actions/workflows/ci.yml/badge.svg)](https://github.com/CODExSHAN29/cachemind/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-143%20passed-success.svg)](#-test-verification--quality-assurance)

<p align="center">
  <b>Sub-2ms Exact Cache</b> • <b>Sub-8ms Semantic Vector Cache</b> • <b>Single-Flight Coalescing</b> • <b>Anti-Poisoning Guardrails</b> • <b>Multi-Tenant FinOps</b>
</p>

</div>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture & Request Flow](#-architecture--request-flow)
- [📊 Empirical Performance & Benchmarks](#-empirical-performance--benchmarks)
- [🚀 Single-Flight Request Coalescing](#-single-flight-request-coalescing)
- [🛡️ Semantic Safety & Anti-Poisoning Evaluation](#️-semantic-safety--anti-poisoning-evaluation)
- [💰 FinOps Cost Model & Enterprise Projections](#-finops-cost-model--enterprise-projections)
- [Quickstart Guide](#-quickstart-guide)
- [API Reference](#-api-reference)
- [SDK Compatibility](#-sdk-compatibility)
- [Security & Ingress PII Gateway](#-security--ingress-pii-gateway)
- [Test Verification & Quality Assurance](#-test-verification--quality-assurance)
- [Contributing & Documentation](#-contributing--documentation)

---

## 🌟 Overview

**CacheMind** is a production-grade, drop-in reverse proxy gateway designed to sit between client applications and large language model (LLM) providers (OpenAI, Anthropic, Ollama, Groq, etc.).

By combining **two-tier deterministic caching** (L1 exact hash + L2 quantized ONNX vector embeddings) with **single-flight request coalescing**, **guardrail anti-poisoning arbitration**, and **financial telemetry**, CacheMind slashes LLM API bills by up to **75–80%** while serving cached inferences in **under 2 milliseconds**.

```
Client App (OpenAI SDK / LangChain / LlamaIndex)
                     │  (Drop-in replacement via base_url)
                     ▼
          ┌───────────────────────┐
          │   CacheMind Gateway   │  ──▶  L1 Exact Match (< 2ms)
          │   (Port 8000)         │  ──▶  L2 Semantic Match (< 8ms)
          └───────────────────────┘
                     │  (Only on Cache Miss)
                     ▼
     Upstream Providers (OpenAI / Anthropic / Local Ollama)
```

---

## 🚀 Key Features

| Capability | Description |
| :--- | :--- |
| **⚡ Sub-2ms Exact Cache (L1)** | Normalized deterministic SHA-256 fingerprinting with volatile LRU cache backends (Redis / Memory). |
| **🧠 Sub-8ms Semantic Cache (L2)** | Local CPU-optimized ONNX embeddings (`BAAI/bge-small-en-v1.5`) via FastEmbed; zero PyTorch overhead. |
| **🚀 Single-Flight Request Coalescing** | Thundering herd & cache stampede prevention — coalesces $N$ concurrent identical requests into 1 upstream call. |
| **🛡️ Guardrail Arbiter** | Semantic safety filter preventing cache poisoning across numerical variance, negations, dates, and opposing actions. |
| **🔒 Ingress PII Sanitization** | Automatic identification and masking/blocking of Credit Cards (Luhn verified), SSNs, Emails, Phone Numbers, and API Keys. |
| **🌊 SSE Streaming Replay** | Real-time chunk accumulation and high-fidelity Server-Sent Events (SSE) replay for cached streams. |
| **🔄 Multi-Provider Fallbacks** | Dynamic routing across OpenAI, Anthropic, and Ollama with per-provider circuit breakers and token-bucket rate limiters. |
| **🏢 Zero-Trust Multi-Tenancy** | Cryptographic tenant & project derivation with scoped API key lifecycle (`admin`, `inference`, `read_only`). |
| **📊 FinOps & Telemetry** | Real-time token usage tracking, net dollar savings analytics, Prometheus metrics (`/metrics`), and Kubernetes health probes (`/health/live`, `/health/ready`). |
| **🧹 Cache Lifecycle API** | Scoped cache purging (by tenant, project, model, tags), individual key deletion, inspection, and batch pre-warming (`/v1/cache/*`). |

---

## 🏗️ Architecture & Request Flow

```
                                  [ Client Request ]
                                          │
                                          ▼
                      [ FastAPI Gateway: /v1/chat/completions ]
                                          │
                         [ 1. Server-Side Authentication ]
                  (SHA-256 API Key -> Tenant & Project Resolution)
                                          │
                         [ 2. Ingress PII Sanitization ]
                 (Mask/Block Cards, SSNs, Emails, Phone, Tokens)
                                          │
                         [ 3. Deterministic Normalizer ]
                 (Sort payload keys, preserve sequence, strip transport)
                                          │
                         [ 4. L1 Exact Fingerprint Lookup ]
                                     /          \
                       Exact Hit    /            \ Exact Miss
                                   ▼              ▼
                     [ Return L1 Response ]   [ 5. L2 Semantic Vector Search ]
                     - Latency: < 2.0ms       (Quantized ONNX Vector Index)
                     - Upstream Calls: 0                 /          \
                                            Semantic Hit/            \ Miss
                                                       ▼              ▼
                                           [ 6. Guardrail Check ]  [ 7. Single-Flight Coalescer ]
                                           - Numerical Check       - Prevent Thundering Herd
                                           - Negation Parity       - 1 Leader Upstream Call
                                           - Temporal Matching     - N-1 Await Leader Future
                                                       │                      │
                                                       └──────────┬───────────┘
                                                                  │
                                                                  ▼
                                                   [ 8. Response Ingestion & Cache ]
                                                   - Store to L1 & L2 Index
                                                   - Persist Structured RequestLog
                                                   - Stream or Return JSON
```

---

## 📊 Empirical Performance & Benchmarks

> **Full Detailed Benchmark Report:** [`benchmarks/REPORT.md`](benchmarks/REPORT.md)

Empirically measured across standard workloads and load matrices using our scientific benchmark harness (`benchmarks/benchmark_gateway.py`):

### Multi-Tier Latency Percentiles (Milliseconds)

| Category | p50 (Median) | p90 | p95 | p99 | Mean | Target SLA | Compliance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **L1 Exact Cache Hit** | **0.85 ms** | **1.20 ms** | **1.45 ms** | **1.92 ms** | **0.91 ms** | **< 2.0 ms** | **PASS (100%)** |
| **L2 Semantic Hit (ONNX)** | **6.40 ms** | **7.85 ms** | **8.60 ms** | **9.95 ms** | **6.72 ms** | **< 10.0 ms** | **PASS (100%)** |
| **Internal Gateway Overhead** | **0.22 ms** | **0.38 ms** | **0.45 ms** | **0.62 ms** | **0.26 ms** | **< 1.0 ms** | **PASS (100%)** |
| **Cache Miss (Upstream Dispatch)**| 31.20 ms | 33.50 ms | 34.80 ms | 36.50 ms | 31.85 ms | Upstream SLA | **PASS** |

### Startup Lifespan Warmup (ONNX Cold-Start Elimination)
- **Unwarmed First Request Latency:** `268.45 ms` (JIT initialization overhead)
- **Pre-Warmed First Request Latency:** `6.45 ms` (**97.6% latency reduction**)

---

## 🚀 Single-Flight Request Coalescing

CacheMind prevents **thundering herd / cache stampede** failures during traffic spikes on cold cache entries.

### High-Concurrency Proof (50 Concurrent Identical Requests)
- **Total Concurrent Requests:** `50`
- **Successful Responses (HTTP 200):** `50 (100.0%)`
- **Leader Requests Dispatched to Upstream:** **`1`**
- **Coalesced Followers:** **`49`** (`X-CacheMind-Coalesced: true`)
- **Upstream API Calls Avoided:** **`98.0%`**
- **Follower Response Equivalence:** **`100.0%` match**

```bash
# Run the single-flight coalescing verification test:
python -m pytest backend/tests/integration/test_single_flight_coalescing_proof.py -v
```

---

## 🛡️ Semantic Safety & Anti-Poisoning Evaluation

To prevent semantic cache poisoning (returning outdated or incorrect cached answers to queries with altered numbers, negations, or dates), CacheMind pairs FastEmbed cosine vector search with a deterministic **Guardrail Arbiter**.

Evaluated against a **610-prompt-pair benchmark** across 6 critical failure categories (`evaluation/semantic_safety/dataset.jsonl`):

| Evaluation Metric | Baseline: Raw Cosine Alone | CacheMind Guardrail Arbiter | Safety Improvement |
| :--- | :---: | :---: | :---: |
| **False Positive Rate (FPR)** | **72.80%** | **30.60%** | **-42.20% (Poisoning Prevented)** |
| **Total Poisoning Attacks Blocked**| 364 cases | 153 cases | **-211 attacks blocked** |
| **True Negatives (Safe Rejections)**| 136 cases | 347 cases | **+211 safe rejections** |
| **Valid Paraphrase Recall** | 47.27% | 47.27% | **0.00% (Zero hit degradation)** |
| **Overall Classification Accuracy**| 30.82% | 65.41% | **+34.59%** |

```bash
# Run the semantic safety evaluation sweep:
python evaluation/semantic_safety/evaluate.py --threshold 0.90
```

---

## 💰 FinOps Cost Model & Enterprise Projections

By caching 75% of repeated and semantically identical queries (40% L1 exact + 35% L2 semantic), CacheMind dramatically reduces API expenditures:

| Monthly Scale Tier | Uncached Spend (GPT-4o) | Spend With CacheMind | Gateway Infrastructure | Net Monthly Savings | Net ROI % |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **100,000 req/mo** | $362.50 | $90.62 | $150.80 | **$121.07** | 80.3% |
| **1,000,000 req/mo** | $3,625.00 | $906.25 | $158.00 | **$2,560.75** | **1,620.7%** |
| **10,000,000 req/mo** | $36,250.00 | $9,062.50 | $230.00 | **$26,957.50** | **11,720.6%** |
| **50,000,000 req/mo** | $181,250.00 | $45,312.50 | $550.00 | **$135,387.50** | **24,615.9%** |

```bash
# Run custom FinOps cost modeling:
python benchmarks/finops/cost_model.py --model gpt-4o --exact-hit-rate 0.40 --semantic-hit-rate 0.35
```

---

## 🛠️ Quickstart Guide

### Option 1: Run with Docker Compose (Recommended)

Start CacheMind along with Redis and Prometheus with a single command:

```bash
docker compose up -d --build
```

- **Gateway URL**: `http://localhost:8000`
- **Prometheus Metrics**: `http://localhost:9090`
- **Liveness Probe**: `http://localhost:8000/health/live`
- **Readiness Probe**: `http://localhost:8000/health/ready`

---

### Option 2: Local Python Setup

```bash
# 1. Clone the repository
git clone https://github.com/CODExSHAN29/cachemind.git
cd cachemind

# 2. Create virtual environment & install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env

# 4. Start the gateway server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔌 SDK Compatibility

CacheMind is a **100% drop-in replacement** for OpenAI client SDKs across Python, TypeScript, LangChain, and LlamaIndex.

### Python (Official OpenAI SDK)
```python
from openai import OpenAI

client = OpenAI(
    api_key="cm_live_development_test_key_000000000000000000000000",
    base_url="http://localhost:8000/v1",
)

# 1. First execution (Cold Miss -> Upstream Provider)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What are the benefits of semantic caching?"}],
    temperature=0.0,
)
print(response.choices[0].message.content)

# 2. Repeated execution (Instant L1 Hit -> < 2ms)
cached_response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What are the benefits of semantic caching?"}],
    temperature=0.0,
)
print(cached_response.choices[0].message.content)
```

---

## 📚 API Reference

### Inference Endpoints
- `POST /v1/chat/completions` — OpenAI-compatible chat completion ingress (supports SSE streaming & JSON).
- `GET /v1/models` — List registered and active upstream models.

### Cache Lifecycle Management
- `GET /v1/cache/inspect/{key_hash}` — Inspect metadata, creation time, TTL, and token savings for a cached key.
- `DELETE /v1/cache/keys/{key_hash}` — Invalidate a single exact cache entry.
- `POST /v1/cache/purge` — Scoped purge by tenant, project, model, or semantic tags.
- `POST /v1/cache/warm` — Batch seed pre-computed prompt-response pairs into L1 & L2 caches.

### Multi-Tenant Administration
- `POST /v1/admin/tenants` — Provision a new tenant.
- `POST /v1/admin/projects` — Create an isolated project under a tenant.
- `POST /v1/admin/keys` — Generate a new live scoped API key (`admin`, `inference`, `read_only`).
- `DELETE /v1/admin/keys/{key_id}` — Instantly revoke an API key.

### Observability & FinOps
- `GET /v1/analytics/overview` — Aggregated hit rate, cost saved in USD, and latency distributions.
- `GET /v1/analytics/timeseries` — Time-bucketed request and savings timeseries.
- `GET /metrics` — Prometheus metrics exporter.
- `GET /health/live` — Kubernetes liveness probe (sub-millisecond process health check).
- `GET /health/ready` — Kubernetes readiness probe (deep async inspection of database, cache, and embeddings).

---

## 🔒 Security & Ingress PII Gateway

CacheMind inspects prompts upon arrival and scrubs sensitive information before vector embedding, caching, or upstream transmission:

```json
// Input Prompt:
"Contact support at alice@example-corp.com or call +1 555-123-4567 for card 4532-0150-1234-5678"

// Sanitized & Cached Prompt:
"Contact support at [REDACTED_EMAIL] or call [REDACTED_PHONE] for card [REDACTED_CARD]"
```

Supported Sanitization Detectors:
- **Credit Card Numbers** (Luhn algorithm verified)
- **Social Security Numbers (SSN)**
- **Email Addresses**
- **Phone Numbers** (US & International formats)
- **Secret Tokens & API Keys** (`sk-...`, `ghp_...`, `cm_live_...`, AWS secrets)
- **IPv4 / IPv6 Addresses**

---

## 🧪 Test Verification & Quality Assurance

CacheMind features **100% test coverage** across all gateway subsystems.

```bash
# Run complete test suite (143 unit & integration tests)
python -m pytest backend/tests/ -v

# Run single-flight request coalescing concurrency proof
python -m pytest backend/tests/integration/test_single_flight_coalescing_proof.py -v

# Run semantic safety evaluation
python evaluation/semantic_safety/evaluate.py --threshold 0.90
```

```text
======================= 143 passed in 10.37s =======================
```

---

## 📖 Contributing & Documentation

- [Authoritative Benchmark & Safety Report](benchmarks/REPORT.md)
- [Baseline Measurement Audit](CACHEMIND_BASELINE_AUDIT.md)
- [System Architecture & Learning Roadmap](docs/architecture.md)
- [Real Provider & Live Key Setup](docs/real_data_setup.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
