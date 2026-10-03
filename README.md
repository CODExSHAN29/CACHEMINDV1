<div align="center">

# ⚡ CacheMind

### Deterministic, Safe & Measurable Semantic Caching Gateway for LLM APIs (v0.1 Public Beta)

[![CI & Test Suite](https://github.com/CODExSHAN29/cachemind/actions/workflows/ci.yml/badge.svg)](https://github.com/CODExSHAN29/cachemind/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-143%20passed-success.svg)](#-test-verification--quality-assurance)

<p align="center">
  <b>Deterministic L1 Exact Hash & L2 Quantized Vector Cache</b> • <b>Single-Flight Request Coalescing</b> • <b>Anti-Poisoning Guardrails</b> • <b>FinOps Telemetry</b>
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
- [💰 FinOps Cost Model & Projections](#-finops-cost-model--projections)
- [Quickstart Guide](#-quickstart-guide)
- [API Reference](#-api-reference)
- [SDK Compatibility](#-sdk-compatibility)
- [Security & Ingress PII Gateway](#-security--ingress-pii-gateway)
- [Test Verification & Quality Assurance](#-test-verification--quality-assurance)
- [Contributing & Documentation](#-contributing--documentation)

---

## 🌟 Overview

**CacheMind** is an open-source reverse proxy gateway designed to sit between client applications and large language model (LLM) providers (OpenAI, Anthropic, Ollama, Groq, etc.).

By combining **two-tier deterministic caching** (L1 exact hash + L2 quantized ONNX vector embeddings) with **single-flight request coalescing**, **guardrail anti-poisoning arbitration**, and **financial telemetry**, CacheMind eliminates redundant API spend (up to **75.0%** cost avoidance on repetitive workloads) while delivering low-latency cached inferences.

```
Client App (OpenAI SDK / LangChain / LlamaIndex)
                     │  (Drop-in replacement via base_url)
                     ▼
          ┌───────────────────────┐
          │   CacheMind Gateway   │  ──▶  L1 Exact Hash Match
          │   (Port 8000)         │  ──▶  L2 Quantized Semantic Vector Match
          └───────────────────────┘
                     │  (Only on Cache Miss)
                     ▼
     Upstream Providers (OpenAI / Anthropic / Local Ollama)
```

---

## 🚀 Key Features

| Capability | Description |
| :--- | :--- |
| **⚡ L1 Exact Cache** | Normalized deterministic SHA-256 fingerprinting with volatile LRU cache backends (Redis / Memory) — p50 client latency of 8.04 ms ($c=1$). |
| **🧠 L2 Semantic Cache** | Local CPU-optimized ONNX embeddings (`BAAI/bge-small-en-v1.5`) via FastEmbed — p50 client latency of 21.81 ms ($c=1$). |
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

```                                      CACHEMIND
                         OpenAI + Anthropic Gateway Platform


┌────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                       │
│                                                                            │
│   OpenAI SDK       Anthropic SDK*       cURL       Apps       Playground   │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          PUBLIC API / EDGE                                 │
│                                                                            │
│   HTTPS                                                                    │
│   Request ID                                                               │
│   Body-size limits                                                         │
│   CORS                                                                     │
│   Global abuse protection                                                  │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                 ┌─────────────────┴──────────────────┐
                 │                                    │
                 ▼                                    ▼
┌──────────────────────────────┐      ┌─────────────────────────────────────┐
│        DATA PLANE            │      │          CONTROL PLANE              │
│                              │      │                                     │
│ /v1/chat/completions         │      │ Login / Signup                      │
│ /v1/responses   [later]      │      │ Workspaces                          │
│ /v1/messages    [later]      │      │ Projects                            │
│                              │      │ API Keys                            │
│ Project API keys ONLY        │      │ Provider Settings                   │
│                              │      │ Usage / Analytics                   │
└───────────────┬──────────────┘      │ Cache Management                    │
                │                     │                                     │
                │                     │ Browser Session ONLY                │
                │                     └──────────────────┬──────────────────┘
                │                                        │
                ▼                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     REQUEST ADMISSION LAYER                                │
│                                                                            │
│   Project API Key Authentication                                           │
│                │                                                           │
│   Tenant / Project Resolution                                              │
│                │                                                           │
│   Gateway RPM / Request Quota                                              │
│                │                                                           │
│   PII Policy                                                               │
│                │                                                           │
│   Request Validation                                                       │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         PROTOCOL ADAPTER                                    │
│                                                                            │
│  OpenAI Chat API ────┐                                                     │
│  OpenAI Responses ───┼──────► Canonical Gateway Request                   │
│  Anthropic Messages ─┘              (internal IR)                         │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    MODEL + PROVIDER RESOLUTION                             │
│                                                                            │
│                     [ Model Catalog ]                                      │
│                                                                            │
│      model alias ─────────► provider ─────────► canonical model             │
│                                                                            │
│                OpenAI                       Anthropic                       │
│                                                                            │
│                 │                              │                            │
│                 └────────── Route Policy ──────┘                            │
│                                                                            │
│    Primary provider                                                        │
│    Optional fallback                                                       │
│    Capability compatibility                                                │
│    Route-policy version                                                    │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         CACHE POLICY                                       │
│                                                                            │
│     tenant                                                                 │
│     project                                                                │
│     provider                                                               │
│     canonical model                                                        │
│     system instructions                                                    │
│     generation parameters                                                  │
│     tools/output contract                                                  │
│     namespace                                                              │
│     cache-policy version                                                   │
│                                                                            │
│                     │                                                      │
│                     ▼                                                      │
│             Exact Request Identity                                         │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
                      ┌────────────────────────┐
                      │      L1 EXACT CACHE    │
                      │         Redis          │
                      └─────────┬──────────────┘
                                │
                 ┌──────────────┴─────────────┐
                 │                            │
             EXACT HIT                     MISS
                 │                            │
                 ▼                            ▼
        Return Cached Response       Semantic Eligibility
                                             │
                                  ┌──────────┴──────────┐
                                  │                     │
                              INELIGIBLE             ELIGIBLE
                                  │                     │
                                  │                     ▼
                                  │           FastEmbed / embedding
                                  │                     │
                                  │                     ▼
                                  │              pgvector search
                                  │                     │
                                  │                     ▼
                                  │             Guardrail Arbiter
                                  │                     │
                                  │          ┌──────────┴──────────┐
                                  │          │                     │
                                  │       L2 HIT                  MISS
                                  │          │                     │
                                  │          ▼                     │
                                  │   Return Cached Response       │
                                  │                                │
                                  └────────────────┬───────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     UPSTREAM ADMISSION                                     │
│                                                                            │
│        Daily project budget                                                │
│        Upstream-request quota                                              │
│        Token budget                                                        │
│        Distributed single-flight                                           │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        PROVIDER EXECUTOR                                   │
│                                                                            │
│                  Typed Provider Interface                                  │
│                                                                            │
│         ┌─────────────────────┐       ┌─────────────────────┐               │
│         │   OpenAI Adapter    │       │ Anthropic Adapter   │               │
│         │                     │       │                     │               │
│         │ request mapper      │       │ request mapper      │               │
│         │ stream mapper       │       │ stream mapper       │               │
│         │ response mapper     │       │ response mapper     │               │
│         │ error mapper        │       │ error mapper        │               │
│         └──────────┬──────────┘       └──────────┬──────────┘               │
│                    │                             │                          │
│                    ▼                             ▼                          │
│                OpenAI API                   Anthropic API                   │
│                                                                            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        RESPONSE PIPELINE                                   │
│                                                                            │
│   Normalize Provider Response                                              │
│              │                                                             │
│   Usage Reconciliation                                                     │
│              │                                                             │
│   Exact Cache Backfill                                                     │
│              │                                                             │
│   Safe Semantic Cache Backfill                                             │
│              │                                                             │
│   Telemetry Event                                                          │
│              │                                                             │
│   Client Protocol Response                                                 │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Empirical Performance & Benchmarks

> **Full Detailed Benchmark Report:** [`benchmarks/REPORT.md`](benchmarks/REPORT.md)

Empirically measured across standard workloads and load matrices using our scientific benchmark harness (`benchmarks/run_full_suite.py`):

### Multi-Tier Client Latency Percentiles (1,000 Requests per Scenario, In-Process ASGI Harness)

| Category | Concurrency ($c$) | Throughput (RPS) | p50 (Median) | p90 | p95 | p99 | Mean | Hit Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **L1 Exact Cache Hit** | 1 | **107.4** | **8.04 ms** | 13.97 ms | 16.19 ms | 21.14 ms | 9.27 ms | **100.0%** |
| **L1 Exact Cache Hit** | 10 | **134.9** | **67.26 ms** | 117.84 ms | 136.08 ms | 157.69 ms | 73.66 ms | **100.0%** |
| **L2 Semantic Hit (FastEmbed ONNX)** | 1 | **46.1** | **21.81 ms** | 30.65 ms | 36.29 ms | 58.20 ms | 21.67 ms | **66.6%** |
| **L2 Semantic Hit (FastEmbed ONNX)** | 10 | **66.6** | **144.81 ms** | 177.30 ms | 194.92 ms | 221.02 ms | 148.86 ms | **66.6%** |
| **Cache Miss (35ms Simulated Delay)** | 1 | **12.0** | **79.50 ms** | 100.99 ms | 108.15 ms | 122.04 ms | 83.04 ms | **0.0%** |
| **Cache Miss (35ms Simulated Delay)** | 10 | **177.1** | **51.81 ms** | 64.93 ms | 70.27 ms | 242.24 ms | 56.12 ms | **0.0%** |

### Startup Lifespan Warmup (FastEmbed ONNX Graph Pre-warming)
- **Unwarmed First Request Latency (Recorded Observation):** `481.55 ms` (JIT / ONNX session initialization)
- **Pre-Warmed First User Request (Recorded Observation):** `12.38 ms` (**97.4% latency reduction**)
*(Note: Recorded from a single cold vs. pre-warmed execution run.)*

---

## 🚀 Single-Flight Request Coalescing

CacheMind prevents **thundering herd / cache stampede** failures during traffic spikes on cold cache entries.

### High-Concurrency Proof (50 Concurrent Identical Requests)
- **Total Concurrent Requests:** `50`
- **Successful Responses (HTTP 200):** `50 (100.0%)`
- **Leader Requests Dispatched to Upstream:** **`1`**
- **Coalesced Followers:** **`49`** (`X-CacheMind-Coalesced: true`)
- **Upstream API Calls Avoided:** **`98.0%`**
- **Coalescing Efficiency:** **`100.0%`**

```bash
# Run the single-flight coalescing verification test:
python -m pytest backend/tests/integration/test_single_flight_coalescing_proof.py -v
```

---

## 🛡️ Semantic Safety & Anti-Poisoning Evaluation

To prevent semantic cache poisoning (returning incorrect cached answers to queries with altered numbers, negations, dates, or opposing actions), CacheMind pairs FastEmbed cosine vector search with a deterministic **Guardrail Arbiter**.

Evaluated against a **610-prompt-pair benchmark** across 6 critical failure categories (`evaluation/semantic_safety/dataset.jsonl`):

| Evaluation Metric | Baseline: Raw Cosine Alone | CacheMind Guardrail Arbiter | Defense Impact |
| :--- | :---: | :---: | :---: |
| **False Positive Rate (FPR)** | **72.80%** (364 / 500) | **30.60%** (153 / 500) | **-42.2 percentage points (~58.0% relative reduction)** |
| **Unsafe Semantic Reuse Decisions Avoided** | — | — | **211 unsafe decisions avoided** |
| **False Positives (Unsafe Cache Hits)** | 364 cases | 153 cases | **-211 cases** |
| **True Negatives (Safe Rejections)** | 136 cases | 347 cases | **+211 safe rejections** |
| **Valid Paraphrase Recall** | **47.27%** (52 / 110) | **47.27%** (52 / 110) | **0.00% (Zero valid hit degradation)** |
| **Precision** | 12.50% | 25.37% | **+12.87 percentage points** |
| **Overall Classification Accuracy** | 30.82% | 65.41% | **+34.59 percentage points** |

```bash
# Run the semantic safety evaluation sweep:
python evaluation/semantic_safety/evaluate.py --threshold 0.90
```

---

## 💰 FinOps Cost Model & Projections

Modeled projections for GPT-4o ($2.50/1M input, $10.00/1M output, 450 avg input tokens, 250 avg output tokens) with a 75.0% total hit rate (40% L1 exact + 35% L2 semantic), deducting baseline gateway infrastructure ($150/mo + $0.000008/req):

| Monthly Request Volume | Uncached Spend (GPT-4o) | Cached Provider Spend | Gateway Infrastructure | Net Monthly Savings | Net ROI % |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **100,000 req/mo** | $362.50 | $90.62 | $150.80 | **$121.07** | 80.3% |
| **500,000 req/mo** | $1,812.50 | $453.12 | $154.00 | **$1,205.38** | 782.7% |
| **1,000,000 req/mo** | $3,625.00 | $906.25 | $158.00 | **$2,560.75** | **1,620.7%** |
| **5,000,000 req/mo** | $18,125.00 | $4,531.25 | $190.00 | **$13,403.75** | **7,054.6%** |
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

# 2. Repeated execution (Instant L1 Hit)
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

```bash
# Run complete test suite (143 unit & integration tests)
python -m pytest backend/tests/ -q

# Run single-flight request coalescing concurrency proof
python -m pytest backend/tests/integration/test_single_flight_coalescing_proof.py -v

# Run semantic safety evaluation
python evaluation/semantic_safety/evaluate.py --threshold 0.90
```

```text
143 passed in 14.26s
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
