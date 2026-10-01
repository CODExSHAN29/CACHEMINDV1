# CacheMind Measurement Baseline Audit

**Date**: 2026-10-01  
**Branch**: main (commit 61943d4)  
**Status**: Post-production-hardening merge

---

## 1. Current Measurable Metrics

| Metric | Source | Collection Method |
|--------|--------|-------------------|
| `cachemind_requests_total` | Prometheus Counter | Per-request, labeled by provider/model/cache_status/tenant |
| `cachemind_gateway_latency_seconds` | Prometheus Histogram | Per-request, buckets up to 10s |
| `cachemind_upstream_latency_seconds` | Prometheus Histogram | Only on MISS, per provider/model |
| `cachemind_cache_lookup_latency_seconds` | Prometheus Histogram | L1 vs L2 level |
| `cachemind_tokens_processed_total` | Prometheus Counter | By token_type (input/output) and cache_status |
| `cachemind_tokens_saved_total` | Prometheus Counter | On EXACT_HIT/L2_HIT, by tenant/model |
| `cachemind_cost_saved_usd_total` | Prometheus Counter | Via `PricingEngine.calculate_savings()` |
| `cachemind_cost_spent_usd_total` | Prometheus Counter | On MISS, via `PricingEngine.calculate_cost()` |
| `cachemind_rate_limit_rejections_total` | Prometheus Counter | By tenant/limit_type |
| `cachemind_circuit_breaker_state` | Prometheus Gauge | CLOSED=0, HALF_OPEN=1, OPEN=2 |

**Response Headers** (from `chat.py`):
- `X-CacheMind-Status`: EXACT_HIT | L2_HIT | MISS | ERROR
- `X-CacheMind-Gateway-Latency-Ms`: End-to-end gateway time
- `X-CacheMind-Lookup-Ms`: Exact cache lookup time
- `X-CacheMind-Upstream-Ms`: Upstream latency (MISS only)
- `X-CacheMind-Similarity`: Cosine similarity (L2_HIT only)
- `X-CacheMind-Coalesced`: true/false (single-flight)

---

## 2. Current Benchmark Gaps

| Gap | Current State |
|-----|---------------|
| **Reproducible benchmark harness** | Single script `scripts/benchmark_latency.py` - runs against live server only, no CI integration, no cold/warm/steady-state separation, no JSON output |
| **Load testing** | None (no k6/Locust) |
| **Concurrency sweep** | Fixed 50 concurrency, 200 iterations |
| **Cost modeling** | `PricingEngine` exists but no benchmark integration |
| **Single-flight proof** | No instrumentation to measure coalescing effect |
| **Cold-start measurement** | No separation of first-request vs steady-state |
| **Hardware documentation** | Not captured in benchmark output |
| **Git commit metadata** | Not recorded in benchmark results |

---

## 3. Current Semantic Safety Gaps

| Gap | Current State |
|-----|---------------|
| **Safety evaluation dataset** | None - no `evaluation/semantic_safety/` directory |
| **Threshold sweep** | Single threshold `VECTOR_SIMILARITY_THRESHOLD=0.92` hardcoded in config |
| **Guardrail vs raw similarity comparison** | Not measured |
| **Unsafe reuse rate** | Not measured |
| **Precision/Recall/F1** | Not computed |
| **Categories covered** | Guardrails implement: system_prompt, negation, numbers, dates. No test dataset for these. |

---

## 4. Cold-Start Behavior

**Embedding Engine** (`backend/semantic/embedding.py`):
- `EmbeddingEngine` is a singleton
- Model loads **lazily on first `embed()` call** (`_ensure_model_loaded()`)
- First call includes: ONNX model load (~50-200ms) + warmup embedding
- Warmup runs `_warmup()` with `"warmup query for cachemind semantic search"`
- Subsequent calls target <3ms (run in thread pool)
- **No startup warmup** - first user request pays full initialization cost

**Configuration**: No `EMBEDDING_WARMUP_ENABLED` setting exists

---

## 5. Health-Check Behavior

| Endpoint | Path | Behavior |
|----------|------|----------|
| **Liveness** | `GET /health` | Returns `{"status": "healthy", "service": "cachemind-gateway", "timestamp": ...}` - no dependency checks |
| **Readiness** | `GET /ready` | Checks DB (`SELECT 1`) + Cache (`cache.ping()`) - returns 200 or 503 |

**Missing from readiness**:
- Embedding model readiness
- Vector index readiness
- Guardrail arbiter readiness
- Volatility engine readiness
- Provider configuration validation (not reachability)

---

## 6. Mock-vs-Real Test Boundaries

| Component | Real Implementation | Mock Implementation | Test Usage |
|-----------|---------------------|---------------------|------------|
| **Embedding** | `EmbeddingEngine` (FastEmbed ONNX) | `MockEmbeddingEngine` (deterministic hash-based) | Unit tests use mock; integration tests can use either via `ALLOW_MOCK_EMBEDDINGS` |
| **Provider** | `OpenAIProvider`, `AnthropicProvider`, `OllamaProvider` | `MockProvider` (deterministic, configurable latency/error) | Unit/integration tests use mock; production uses real |
| **Vector Index** | `VectorIndex` (hnswlib/numpy) | `MockVectorIndex` | Unit tests use mock; integration tests use real |
| **Cache Backend** | `RedisCacheBackend` / `MemoryCacheBackend` | In-memory in tests | Tests use memory backend |

**Config Gates** (`config.py`):
- `ALLOW_MOCK_PROVIDERS=true` (dev/test only)
- `ALLOW_MOCK_EMBEDDINGS=true` (dev/test only)
- Production validation rejects both if `ENVIRONMENT=production`

---

## 7. Exact / Semantic Request Headers

**Exact Hit** (`chat.py` lines 185-195):
```
X-CacheMind-Status: EXACT_HIT
X-CacheMind-Request-ID: <uuid>
X-CacheMind-Exact-Hash: <hash>
X-CacheMind-Gateway-Latency-Ms: <ms>
X-CacheMind-Lookup-Ms: <ms>
X-CacheMind-Provider: <provider>
X-CacheMind-Model: <model>
X-CacheMind-Fallback-Hops: 0
```

**Semantic Hit** (`chat.py` lines 293-304):
```
X-CacheMind-Status: L2_HIT
X-CacheMind-Request-ID: <uuid>
X-CacheMind-Exact-Hash: <hash>
X-CacheMind-Similarity: <0.XXXX>
X-CacheMind-Gateway-Latency-Ms: <ms>
X-CacheMind-Lookup-Ms: <ms>
X-CacheMind-Provider: <provider>
X-CacheMind-Model: <model>
X-CacheMind-Fallback-Hops: 0
```

**Miss** (`chat.py` lines 494-506):
```
X-CacheMind-Status: MISS
X-CacheMind-Request-ID: <uuid>
X-CacheMind-Exact-Hash: <hash>
X-CacheMind-Gateway-Latency-Ms: <ms>
X-CacheMind-Lookup-Ms: <ms>
X-CacheMind-Upstream-Ms: <ms>
X-CacheMind-Provider: <provider>
X-CacheMind-Model: <model>
X-CacheMind-Fallback-Hops: <n>
X-CacheMind-Coalesced: true/false
```

---

## 8. Key Files for Phase 1+

| Phase | Target Files |
|-------|-------------|
| **1. FastEmbed Warmup** | `backend/app/main.py` (lifespan), `backend/semantic/embedding.py`, `backend/app/config.py` |
| **2. Health Endpoints** | `backend/api/v1/health.py`, `backend/semantic/factory.py` (ping) |
| **3. Benchmark Harness** | New: `benchmarks/benchmark_gateway.py`, `benchmarks/workloads/*.jsonl` |
| **4. Load Testing** | New: `benchmarks/load/` (k6 scripts) |
| **5-7. Safety Evaluation** | New: `evaluation/semantic_safety/` |
| **8-9. Workload/Cost** | New: `evaluation/support_workload/`, integrate with `analytics/pricing.py` |
| **10. Single-Flight** | `backend/caching/coalescer.py` (add metrics), `chat.py` |
| **11. Report** | New: `benchmarks/REPORT.md` |

---

## 9. Risk Summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Cold-start latency on first semantic request | High | Phase 1: startup warmup |
| Readiness doesn't verify semantic subsystem | Medium | Phase 2: extend `/ready` |
| No reproducible benchmark evidence | Critical | Phase 3-4: new harness + load tests |
| No semantic safety measurement | Critical | Phase 5-7: dataset + evaluator + threshold sweep |
| Single-flight not proven under concurrency | High | Phase 10: explicit test |
| README claims unsupported numbers | Medium | Phase 11: replace with measured data |

---

## 10. Next Phase

**Phase 1 — FastEmbed Startup Warm-Up**

Implementation plan:
1. Add `EMBEDDING_WARMUP_ENABLED` config (default true)
2. In `main.py` lifespan, after `init_db()`, initialize embedding engine and run warmup
3. Record warmup duration in logs/metrics
4. Expose embedding readiness in `/health/ready`
5. Add unit tests for warmup behavior
6. Measure cold-start before/after