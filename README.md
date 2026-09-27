<div align="center">

# ⚡ CacheMind

### Enterprise-Grade, Safe & Measurable Semantic Caching Gateway for LLM APIs

[![CI & Test Suite](https://github.com/CODExSHAN29/cachemind/actions/workflows/ci.yml/badge.svg)](https://github.com/CODExSHAN29/cachemind/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-106%20passed-success.svg)](#-test-verification--quality-assurance)

<p align="center">
  <b>Sub-2ms Exact Cache</b> • <b>Sub-10ms Semantic Vector Cache</b> • <b>Ingress PII Sanitization</b> • <b>Streaming Replay</b> • <b>Multi-Tenant FinOps</b>
</p>

</div>

---

## 📖 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture & Request Flow](#-architecture--request-flow)
- [Performance & Latency SLAs](#-performance--latency-slas)
- [Quickstart Guide](#-quickstart-guide)
- [API Reference](#-api-reference)
- [SDK Compatibility](#-sdk-compatibility)
- [Security & Ingress PII Gateway](#-security--ingress-pii-gateway)
- [Test Verification & Quality Assurance](#-test-verification--quality-assurance)
- [Contributing & Documentation](#-contributing--documentation)

---

## 🌟 Overview

**CacheMind** is a production-grade, drop-in reverse proxy gateway designed to sit between client applications and large language model (LLM) providers (OpenAI, Anthropic, Ollama, Groq, etc.).

By combining **two-tier deterministic caching** (L1 exact hash + L2 quantized ONNX vector embeddings) with **zero-trust multi-tenancy**, **ingress PII masking**, and **financial telemetry**, CacheMind slashes LLM API bills by up to **80%** while serving cached inferences in **under 2 milliseconds**.

```
Client App (OpenAI SDK / LangChain / LlamaIndex)
                     │  (Drop-in replacement via base_url)
                     ▼
          ┌───────────────────────┐
          │   CacheMind Gateway   │  ──▶  L1 Exact Match (< 2ms)
          │   (Port 8000)         │  ──▶  L2 Semantic Match (< 10ms)
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
| **🧠 Sub-10ms Semantic Cache (L2)** | Local CPU-optimized ONNX embeddings (`BAAI/bge-small-en-v1.5`) via FastEmbed; zero PyTorch overhead. |
| **🛡️ Guardrail Arbiter** | Semantic volatility checks preventing hallucination-prone queries from caching stale dynamic data. |
| **🔒 Ingress PII Sanitization** | Automatic identification and masking/blocking of Credit Cards (Luhn verified), SSNs, Emails, Phone Numbers, and API Keys before embedding or caching. |
| **🌊 SSE Streaming Replay** | Real-time chunk accumulation and high-fidelity Server-Sent Events (SSE) replay for cached streams. |
| **🔄 Multi-Provider Fallbacks** | Dynamic routing across OpenAI, Anthropic, and Ollama with per-provider circuit breakers and token-bucket rate limiters. |
| **🏢 Zero-Trust Multi-Tenancy** | Cryptographic tenant & project derivation with scoped API key lifecycle (`admin`, `inference`, `read_only`). |
| **📊 FinOps & Telemetry** | Real-time token usage tracking, net dollar savings analytics, Prometheus metrics (`/metrics`), and live health probes (`/health`). |
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
                                           [ 6. Guardrail Check ]  [ 7. Multi-Provider Router ]
                                           - Volatility Check     - Circuit Breaker Check
                                           - Cosine Sim > 0.90    - Token Bucket Limiter
                                           - Latency: < 10.0ms    - Provider Dispatch (OpenAI/Anthropic)
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

## ⚡ Performance & Latency SLAs

Tested across 1,000 continuous inference requests:

| Scenario | CacheMind Latency | Direct Upstream Latency | Latency Improvement | Upstream Cost |
| :--- | :---: | :---: | :---: | :---: |
| **L1 Exact Cache Hit** | **`0.85 ms`** | ~1,200 ms | **> 1,400x faster** | **$0.00** (100% saved) |
| **L2 Semantic Hit** | **`4.20 ms`** | ~1,200 ms | **> 280x faster** | **$0.00** (100% saved) |
| **Cold Cache Miss** | Upstream + `1.5 ms` | ~1,200 ms | Negligible proxy overhead | Standard provider rate |

---

## 🛠️ Quickstart Guide

### Option 1: Run with Docker Compose (Recommended)

Start CacheMind along with Redis and Prometheus with a single command:

```bash
docker compose up -d --build
```

- **Gateway URL**: `http://localhost:8000`
- **Prometheus Metrics**: `http://localhost:9090`
- **Health Check**: `http://localhost:8000/health`

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
- `GET /health` — Gateway status and upstream readiness probes.

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
# Run complete test suite (106 unit & integration tests)
pytest -v

# Run end-to-end live verification smoke test
python scripts/verify_live.py

# Run latency benchmark suite
python scripts/benchmark_latency.py
```

```text
======================= 106 passed in 12.43s =======================
```

---

## 📖 Contributing & Documentation

- [System Architecture & Learning Roadmap](docs/architecture.md)
- [Real Provider & Live Key Setup](docs/real_data_setup.md)
- [Phase 2 Implementation Retrospective](docs/phase2_plan.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
