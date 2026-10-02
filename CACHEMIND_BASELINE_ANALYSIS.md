# CacheMind — Codebase Analysis Report

**Date:** 2026-10-02  
**Branch:** `feat/premium-editorial-ui` (`3851fa6`)  
**Status:** Clean working tree, tests green (149 passed)

---

## 1. What this is

CacheMind is a production-grade **OpenAI-compatible reverse proxy** that sits between client applications and LLM providers (OpenAI / Anthropic / Ollama). It is a **semantic + exact caching gateway** with multi-tenancy, PII sanitization, guardrails, single-flight coalescing, rate limiting, circuit-breaker fallbacks, and FinOps telemetry.

It is **not** a toy: it has 149 passing tests, an empirical benchmark harness, a 610-prompt semantic safety evaluation suite, a FinOps cost model, Alembic migrations, a Helm chart, a Next.js dashboard, a Python SDK, and a TypeScript SDK.

---

## 2. High-level architecture

```
Client (OpenAI SDK) ──► FastAPI Gateway (:8000) ──► [Auth] ──► [PII Sanitizer]
                                                  ──► [Normalizer] ──► [L1 Exact Hash]
                                                                 ├── Hit  ->  return cached (0.6ms p50)
                                                                 └── Miss ──► [L2 Semantic Vector]
                                                                            ├── Hit + Guardrail PASS -> return cached (18ms)
                                                                            └── Miss/GUARDRAIL FAIL -> [Routing Engine]
                                                                                                         ──► [UPSTREAM PROVIDER]
                                                                                                          ──► [Dual Backfill L1+L2]
                                                                                                          ──► [Telemetry DB]
```

### Request flow (the money path: `backend/api/v1/chat.py:32`) — 8 numbered stages

| Stage | Where | What |
|-------|-------|------|
| 1 | `chat.py` L49-95 | Parse OpenAI payload → `NormalizedInferenceRequest`; apply namespace/tags headers; **PII sanitize** each message |
| 2 | `chat.py` L97-123 | **Rate-limit check** (RPM + TPM) via token-bucket limiter |
| 3 | `chat.py` L125-132 | Compute **exact request hash** = `SHA256(tenant\|project\|canonical_body)` |
| 4 | `chat.py` L134-212 | **L1 exact cache lookup** → `EXACT_HIT` or fall through |
| 5 | `chat.py` L214-330 | **L2 semantic lookup**: embed last-user-text, vector search (HNSW, cos≥0.92), **Guardrail Arbiter** check |
| 6 | `chat.py` L332-424 | **Cache miss** → single-flight coalesce 50 concurrent dupes into 1 upstream call |
| 7 | `chat.py` L426-483 | **Dual backfill**: TTL from Volatility Engine → store to L1 + L2 |
| 8 | `chat.py` L487-533 | **Telemetry**: write `RequestLog` row + Prometheus metrics + response headers |

### Tenants & projects (zero-trust)
- `auth/dependencies.py` parses Bearer token or `api-key` header → SHA-256 hash lookup in DB → resolves `Tenant → Project → APIKey`.
- Client-spoofed headers like `X-Tenant-ID` are **discarded**; identity derives **only** from the verified key.
- Master admin key bypass (`ADMIN_MASTER_KEY`) exists; production config validator refuses known-default keys (`settings.py:123`).

---

## 3. Two-tier cache engine

**L1 — Exact cache** (`caching/`)
- `fingerprint.py` — deterministic canonicalizer: recursively sorts dict keys, preserves message order, strips transport-only fields (`stream`, `user`, etc.). Hash = `SHA256("tenant:{tid}|proj:{pid}|body:{canon}")`.
- `factory.py` — singleton backend selector: `InMemoryExactCache` or `RedisExactCache` (fail-open on Redis down).
- Project-isolated keyspace: `cm:v1:exact:{project_id}:{hash}`.

**L2 — Semantic cache** (`semantic/`)
- `embedding.py` — FastEmbed ONNX (`bge-small-en-v1.5`, 384-dim, sub-3ms). Mock engine with `register_similar()` for test determinism.
- `factory.py` — `SemanticCacheService` composing embedding + vector backend + arbiter + volatility engine. Singleton via `get_semantic_cache_service()`.
- `vector_index.py` — in-memory HNSW/Cosine vector index (`SemanticCandidate`). PgVector and Qdrant backends (`pgvector_backend.py`, `qdrant_backend.py`) implement the same `SemanticCacheBackend` Protocol.
- `backend.py` — Protocol interface (7 async methods: insert, search, delete, stats, ping, clear, scope/project/tenant-scoped deletes).

**Guardrail Arbiter** (`guardrails/arbiter.py`)
- 4 deterministic checks before returning an L2 hit:
  1. System prompt exact match
  2. Negation/action polarity (opposing action pairs: cancel/renew, delete/create, etc.)
  3. Numbers match exactly (normalizes `$50` vs `50.0` vs `1,000`)
  4. Dates match (ISO, US, named months, standalone years)
- Evaluated against a **610-prompt benchmark** — reduces false-positive rate from 72.8% → 30.6% with zero degradation in valid paraphrase recall.

**Volatility Engine** (`guardrails/volatility.py`)
- Regex/keyword classifier → 3 tiers: `volatile` (5m TTL), `semi-static` (24h), `evergreen` (30d).

---

## 4. Routing & resilience

`routing/engine.py` — `RoutingEngine` with:
- Model→provider resolution (`resolve_provider_for_model`): gpt-*→openai, claude→anthropic, llama/mistral/etc→ollama.
- **Circuit-breaker registry** (`resilience/circuit_breaker.py`) per `provider:model` — fast-fail on OPEN.
- **Automatic fallback** chain (only when `allow_provider_fallback=true`): openai↔anthropic↔ollama.
- Streaming via `execute_stream()` — pre-fetches first chunk to validate stream health; if it dies, rolls to next target.
- Single-flight coalescer (`caching/coalescer.py`) — 50 concurrent identical requests → 1 upstream call. Verified by `test_single_flight_coalescing_proof.py`.

---

## 5. Security & PII

`security/pii.py` — `PIISanitizer`:
- Regex patterns for: credit cards (Luhn-verified), SSNs, emails, phone numbers, API keys/tokens (`sk-`, `ghp_`, `cm_`, AWS `AKIA`, Bearer tokens, PEM private keys), IPv4.
- Modes: `mask` (default, replaces in text), `block` (raises `PIIBlockedException` → HTTP 400), `passthrough`, or fully disabled.
- Span-deduplication so overlapping matches resolve to the highest-priority entity.

`auth/identity.py` — `AuthenticatedIdentity` dataclass carrying `tenant_id`, `project_id`, `role`, `key_prefix`.

---

## 6. Telemetry & FinOps

`metrics/collector.py` — Prometheus metrics:
- Counters: `cachemind_requests_total`, `tokens_processed_total`, `tokens_saved_total`, `cost_saved_usd_total`, `cost_spent_usd_total`, `rate_limit_rejections_total`, `errors_total`.
- Histograms: `gateway_latency_seconds` (12 buckets, 1ms→10s), `upstream_latency_seconds`, `cache_lookup_latency_seconds`.
- Gauge: `cachemind_circuit_breaker_state`.

`telemetry/service.py` — async `RequestLog` DB writes (SQLAlchemy) with request_id, cache_status, latencies, token counts, similarity score, guardrail pass/fail.

`analytics/service.py` + `analytics/pricing.py` — `/v1/analytics/*` endpoints: overview (hit rate %, p50/p95/p99, USD saved), timeseries, per-model breakdown, paginated audit logs with search.

`backend/api/v1/` modules: `chat.py`, `admin.py`, `analytics.py`, `cache_endpoint.py`, `billing.py`, `dashboard.py`, `health.py`, `metrics_endpoint.py`, `models_endpoint.py`, `auth.py`.

**Response headers** on every request: `X-CacheMind-Status` (EXACT_HIT|L2_HIT|MISS), `X-CacheMind-Request-ID`, `X-CacheMind-Exact-Hash`, `X-CacheMind-Gateway-Latency-Ms`, `X-CacheMind-Lookup-Ms`, `X-CacheMind-Upstream-Ms`, `X-CacheMind-Similarity`, `X-CacheMind-Provider`, `X-CacheMind-Model`, `X-CacheMind-Fallback-Hops`, `X-CacheMind-Coalesced`.

---

## 7. Backend module map (by line count, top contributors)

| Module | Lines | Role |
|--------|-------|------|
| `api/v1/auth.py` | 789 | Signup/login/logout, workspace/project/key CRUD, session management |
| `semantic/vector_index.py` | 775 | In-memory HNSW + cosine vector index |
| `api/v1/chat.py` | 534 | **Main gateway endpoint** — the 8-stage flow above |
| `api/v1/dashboard.py` | 487 | Dashboard summary, project analytics endpoints |
| `analytics/service.py` | 432 | Aggregated query service for overview/timeseries/model/logs |
| `semantic/pgvector_backend.py` | 424 | PostgreSQL pgvector backend impl |
| `semantic/factory.py` | 392 | Singleton factory for semantic cache components |
| `db/repositories.py` | 387 | Async CRUD repos: User, Tenant, Project, APIKey, Session, RequestLog |
| `guardrails/arbiter.py` | 303 | Semantic safety guardrail checks |
| `auth/dependencies.py` | 288 | FastAPI auth deps (Bearer / cookie / api-key) |

Total backend: **~10.3K lines** Python across 60+ modules.

### Backend package layout
```
backend/
├── api/v1/        # 8 HTTP routers (chat, auth, admin, analytics, cache, billing, dashboard, health, metrics, models)
├── app/           # config.py (pydantic-settings, 30+ env vars, production fail-closed validator) + main.py (FastAPI lifespan)
├── auth/          # API key hashing (SHA-256), session tokens, identity resolution
├── billing/       # Stripe webhook integration, pricing tiers
├── caching/       # L1 exact cache: memory + Redis backends, fingerprint, factory, warmer, invalidation, coalesce
├── db/            # Models (SQLAlchemy, 8 tables), async session, repositories
├── guardrails/    # Arbiter (safety) + Volatility (TTL) engines
├── metrics/       # Prometheus collector
├── normalization/ # Canonicalizer (deterministic JSON sort) + OpenAI adapter
├── providers/     # openai/anthropic/ollama/mock providers, registry, routing
├── ratelimit/     # Token-bucket RPM+TPM limiter
├── resilience/    # Circuit-breaker registry
├── routing/       # RoutingEngine with fallback chain
├── security/      # PII sanitizer
├── semantic/      # L2 vector backends: memory/pgvctor/qdrant, embedding engine, factory
├── streaming/     # SSE accumulator for cached/streaming responses
├── telemetry/     # RequestLog service
└── tests/         # 149 tests (integration + unit)
```

---

## 8. Frontend (dashboard-app)

- **Next.js 15** app router (`/app/` pages: landing, login, signup, dashboard, analytics, billing, cache, keys, playground).
- **`components/three/CacheRibbon.tsx`** — the WebGL animated ribbon (hero landing visual).
- **`lib/api.ts`** — typed API client hitting `/v1/*` (auth, analytics, cache, billing, playground inference).
- **`lib/useScopedData.ts`** — scoped data fetching hook tied to tenant/project context.
- **`context/AuthContext.tsx`** — session cookie-based auth context for the dashboard UI.
- Tailwind CSS + lucide-react icons.
- Build output exists in `.next/` and `.next-preview/`.

**Notable:** The current branch (`feat/premium-editorial-ui`) is a **redesign** — git diff vs main shows 46 files changed, mostly frontend, deleting old landing components (`ArchitectureFlow`, `CodeShowcase`, `HeroConstellation`, `VectorClusterVisualizer`) and replacing with a trimmed editorial layout. Backend is largely untouched by this branch.

---

## 9. SDKs

- **Python SDK** (`sdk/python/cachemind/`): `client.py`, `async_client.py`, `models.py`, `exceptions.py` — thin wrappers around httpx/OpenAI-compatible interface.
- **TypeScript SDK** (`sdk/typescript/src/`): `client.ts`, `index.ts`, `types.ts` — typed client for Node/browser.

---

## 10. Infrastructure & deployment

- **Dockerfile** — Python 3.14-slim FastAPI app, gunicorn+uvicorn workers.
- **docker-compose.yml** — gateway + postgres:16 + redis:7.2 + prometheus.
- **helm/cachemind/** — K8s Chart.yaml, deployment, service, configmap, values.
- **prometheus.yml** — scrape config for `/metrics`.
- **alembic/** — 3 migrations: `0001_initial_schema`, `0002_pgvector_semantic_cache`, `0003_auth_workspaces_sessions`.

---

## 11. Benchmarks & evaluation

- **`benchmarks/`** — `run_full_suite.py`, `benchmark_gateway.py`, `finops/cost_model.py`, `load/run_load_matrix.py`, `workloads/generate_customer_support.py`.
- **`evaluation/semantic_safety/`** — 610-prompt dataset, `evaluate.py` with threshold sweep, `generate_dataset.py`.
- Documented results: L1 p50 = **8.04 ms**, L2 p50 = **21.81 ms**, single-flight 50→1 upstream (98% savings), FinOps ROI up to 24,615% at 50M req/mo.

---

## 12. Configuration

`backend/app/config.py` — `Settings(BaseSettings)` with 30+ fields. Key defaults:
- `ENVIRONMENT=development`, `DATABASE_URL=sqlite+aiosqlite:///./cachemind.db`
- `CACHE_BACKEND=memory` (redis in prod), `VECTOR_BACKEND=memory` (pgvector/qdrant in prod)
- `ALLOW_MOCK_PROVIDERS=True`, `ALLOW_MOCK_EMBEDDINGS=True` (gated by production validator)
- `PII_MASKING_MODE=mask`, `DEFAULT_CACHE_TTL_SECONDS=86400`
- `ADMIN_MASTER_KEY="cm_admin_master_secret_key_..."` (validator rejects this in production)
- Production validator (`validate_production_configuration`): refuses SQLite, memory cache, memory vector, mock providers, and weak admin keys.

---

## 13. Current branch state

`feat/premium-editorial-ui` is **frontend-focused only** (+ `design-qa.md`). It:
- Removes 7 old landing-page components (~2,200 loc deleted).
- Redesigns `app/page.tsx` with a simplified editorial WebGL landing.
- Adds `components/AuthScreen.tsx`, `components/GatewayHealth.tsx`, `components/Telemetry.tsx`, `components/three/CacheRibbon.tsx`.
- **No backend logic changes.** All 149 tests still pass.

---

## 14. One weakness I spotted

`dashboard-app/lib/api.ts:252` reads header `x-cachemind-cache` (lowercase "cache"), but `backend/api/v1/chat.py` emits `X-CacheMind-Status`. **HTTP headers are case-insensitive** in practice (browsers/`fetch` normalize), but the names differ ("cache" vs "status") — the frontend will always get `undefined` for cache status. Minor, but it's a real bug if anyone clicks "Open telemetry".

---

## 15. Summary

| Area | Status | Tech |
|------|--------|------|
| Gateway core | ✅ Complete | FastAPI, async |
| L1 exact cache | ✅ Complete | Redis/Memory, SHA-256 |
| L2 semantic cache | ✅ Complete | FastEmbed ONNX, HNSW/pgvector/qdrant |
| Guardrails | ✅ Complete | Negation/number/date/system-prompt checks |
| Single-flight | ✅ Complete & proven | 50→1 coalescing test |
| Multi-provider | ✅ Complete | OpenAI/Anthropic/Ollama + circuit breaker + fallback |
| Auth & tenancy | ✅ Complete | Master key, API key, session cookies |
| PII sanitization | ✅ Complete | Luhn cards, SSN, email, phone, tokens, IP |
| Telemetry | ✅ Complete | Prometheus + SQL RequestLog |
| FinOps | ✅ Modeled | Savings calculator, pricing engine |
| Dashboard | ✅ Present | Next.js 15, app router |
| SDKs | ✅ Present | Python + TypeScript |
| Infra | ✅ Present | Docker, Helm, Alembic, Prometheus |
| Tests | ✅ Green | 149 passed |
| Benchmarks | ✅ Empirical | Full suite + 610-prompt safety eval |
| Current branch | 🚧 Frontend only | Editorial redesign, backend clean |

This is a substantial, production-architected codebase with strong test coverage, empirical validation, and a clear roadmap. The backend is stable; the current branch iterates on the frontend UI layer only.

→ **skipped: nothing material; this codebase is unusually complete for a "v0.1" project. Add when: product wants real-time vector index sync to pgvector, or a persistent L1 Redis layer for multi-instance scaling.**
