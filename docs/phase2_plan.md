# CacheMind Phase 2: Semantic Caching & Guardrails — Implementation Plan

**Source doc:** `CACHEMIND_SYSTEM_DESIGN_AND_LEARNING_ROADMAP.md` (Section 3, 5.4, 5.5, 5.6)
**Phase 1 status:** ✅ Complete & Verified (20/20 tests passing)
**Goal:** Sub-3ms local ONNX embeddings, embedded vector index (HNSW/Cosine), entity & negation guardrails with zero false-positive hits.

---

## What Phase 2 Adds (Architecture Diff vs Phase 1)

Phase 1 flow: `Ingress → Auth → Canonicalize → Exact Hash → L1 Cache (Redis/Mem) → MISS → Upstream → Store L1`

Phase 2 inserts **two new stages** after L1 miss and before upstream:

```
L1 MISS
  │
  ▼
┌─────────────────────────────────────┐
│ 5b. L2: Semantic Cache Engine       │  ← NEW MODULE
│     - FastEmbed ONNX embedding      │
│     - HNSW vector index             │
│     - Cosine similarity ≥ 0.92      │
└──────────────┬──────────────────────┘
               │
         ┌─────┴─────┐
      HIT│           │MISS
         ▼           ▼
  ┌─────────────┐  │
  │ 6. Guardrail│  │
  │   Arbiter   │  │
  │  - Negation │  │
  │  - Numbers  │  │
  │  - Dates    │  │
  │  - System   │  │
  │  Prompts    │  │
  └──────┬──────┘  │
    PASS│    FAIL   │
         ▼         ▼
  [ L2 Hit ]  [ Reject → Upstream ]
    (<8ms)
```

---

## Sub-Project 1: New `semantic/` Package

### 1.1 `backend/semantic/__init__.py`

Empty init; exposes the public API.

### 1.2 `backend/semantic/embedding.py`

**Purpose:** Local FastEmbed ONNX embedding generation (< 3ms).

**Key design decisions:**
- Use `fastembed` Python package (`TextEmbedding` from `fastembed`).
- Model: `BAAI/bge-small-en-v1.5` (384-dim) — matches the spec's "Sub-3ms on CPU".
- Singleton pattern (model loads once at startup), consistent with how `get_provider()` and `get_cache_backend()` work in Phase 1.

**Interface to implement:**

```python
class EmbeddingEngine:
    """Singleton; loads FastEmbed model on first access."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None: ...

    async def embed(self, text: str) -> List[float]:
        """Returns 384-dim float list. Must complete in < 3ms after warmup."""
        ...

    async def embed_batch(self, texts: List[str]) -> List[List[float]]: ...
```

**Factory functions** (matching Phase 1 pattern):
- `get_embedding_engine() -> EmbeddingEngine`
- `set_embedding_engine(engine: EmbeddingEngine) -> None`  (for test injection)

**Dependencies to add in `pyproject.toml`:**
```toml
fastembed = "^0.3.0"
numpy = "^1.26.0"
```

### 1.3 `backend/semantic/vector_index.py`

**Purpose:** In-memory HNSW vector index with cosine similarity search.

**Design decision:** Use `hnswlib` library for true HNSW O(log N) search, or fall back to `numpy`-based brute-force if `hnswlib` fails to install on Windows (the spec says "in-memory vector index" — brute-force is acceptable for <10k entries, but we should try HNSW first).

**Interface to implement:**

```python
class VectorIndex:
    """
    Stores vector entries and searches by cosine similarity.
    Each entry is bound to a scope_hash (tenant+project+model+system_prompt)
    so cache namespaces never leak across models or system prompts.
    """

    def __init__(self, dim: int = 384, similarity_threshold: float = 0.92) -> None: ...

    async def insert(
        self,
        scope_hash: str,
        exact_request_hash: str,
        vector: List[float],
        response_payload: Dict[str, Any],
        cached_response: CachedResponse,
    ) -> None: ...
        """Stores vector + metadata. Called on L1 miss after upstream inference."""

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
    ) -> List[SemanticCandidate]:
        """
        Returns candidates with cosine similarity >= threshold, sorted descending.
        Only searches within the same scope_hash (same model + system prompt).
        """
        ...

    async def delete(self, exact_request_hash: str) -> bool: ...
    async def ping(self) -> bool: ...
    async def clear(self) -> None: ...
```

**Supporting dataclass:**
```python
@dataclass(frozen=True)
class SemanticCandidate:
    exact_request_hash: str
    scope_hash: str
    similarity: float          # cosine similarity score [0.0, 1.0]
    response_payload: Dict[str, Any]
    cached_response: CachedResponse
    created_at: float
```

**Factory functions:**
- `get_vector_index() -> VectorIndex`
- `set_vector_index(idx: VectorIndex) -> None`

### 1.4 `backend/semantic/models.py`

**Purpose:** Data models for L2 semantic caching.

```python
@dataclass(frozen=True)
class SemanticCandidate: ...      # as above

class SemanticCacheEntry(BaseModel):
    """Full entry stored in the vector index with all metadata."""
    exact_request_hash: str
    scope_hash: str
    vector: List[float]
    response_payload: Dict[str, Any]
    model: str
    system_prompt: str
    created_at: float
    ttl_seconds: int
    hit_count: int = 0

class SemanticCacheHitResult(BaseModel):
    """Result returned when guardrails pass."""
    exact_request_hash: str
    similarity: float
    response_payload: Dict[str, Any]
```

### 1.5 `backend/semantic/backend.py`

**Purpose:** `SemanticCacheBackend` protocol (mirrors `ExactCacheBackend`).

```python
@runtime_checkable
class SemanticCacheBackend(Protocol):
    async def search(
        self, scope_hash: str, query_vector: List[float], top_k: int = 5
    ) -> List[SemanticCandidate]: ...

    async def insert(
        self, scope_hash: str, entry: SemanticCacheEntry
    ) -> None: ...

    async def delete(self, exact_request_hash: str) -> bool: ...

    async def ping(self) -> bool: ...
    async def clear(self) -> None: ...
```

### 1.6 `backend/semantic/factory.py`

**Purpose:** Singleton provider for `VectorIndex` (matches `caching/factory.py` pattern).

```python
def get_vector_index() -> VectorIndex: ...
def set_vector_index(idx: VectorIndex) -> None: ...
```

---

## Sub-Project 2: `backend/guardrails/` Package

### 2.1 `backend/guardrails/__init__.py`

### 2.2 `backend/guardrails/arbiter.py`

**Purpose:** The Guardrail Arbiter — the "brain" that decides whether a semantic candidate is safe to return.

**Design (mirrors the spec's Section 5.5 diagram):**

The arbiter compares the **candidate query text** (the cached query) against the **incoming query text** on four dimensions:

1. **Negation Check** — Different verbs/modal words = reject.
   - Keywords to classify: `cancel`, `renew`, `confirm`, `revoke`, `delete`, `remove`, `add`, `create`, `update`, `change`.
   - If negation status differs → **REJECT**.

2. **Number Check** — Different numeric values = reject.
   - Extract all numbers from both texts via regex `\d+`.
   - If sets differ → **REJECT**.

3. **Date Check** — Different dates = reject.
   - Extract dates via regex `\b\d{4}-\d{2}-\d{2}\b`, `\b\d{1,2}/\d{1,2}/\d{2,4}\b`, and month-name patterns.
   - If sets differ → **REJECT**.

4. **System Prompt Match** — Exact string comparison required.
   - If system prompts differ → **REJECT**.

**Interface:**

```python
@dataclass(frozen=True)
class GuardrailDecision:
    passed: bool                # True = safe to return L2 hit
    reason: str                 # "PASS" or specific failure reason
    failed_checks: List[str]    # e.g., ["negation", "number"]

class GuardrailArbiter:
    async def evaluate(
        self,
        incoming_text: str,
        candidate_text: str,
        incoming_system_prompt: str,
        candidate_system_prompt: str,
    ) -> GuardrailDecision: ...
```

**Implementation detail — the `evaluate` method:**
```python
async def evaluate(self, incoming_text, candidate_text, incoming_sp, candidate_sp) -> GuardrailDecision:
    checks_passed = []
    failed = []

    # 1. System prompt exact match (must match exactly)
    if incoming_sp.strip() != candidate_sp.strip():
        failed.append("system_prompt")
    else:
        checks_passed.append("system_prompt")

    # 2. Negation check
    if not _negation_match(incoming_text, candidate_text):
        failed.append("negation")
    else:
        checks_passed.append("negation")

    # 3. Number check
    if not _numbers_match(incoming_text, candidate_text):
        failed.append("number")
    else:
        checks_passed.append("number")

    # 4. Date check
    if not _dates_match(incoming_text, candidate_text):
        failed.append("date")
    else:
        checks_passed.append("date")

    return GuardrailDecision(
        passed=len(failed) == 0,
        reason="PASS" if not failed else f"FAIL: {', '.join(failed)}",
        failed_checks=failed,
    )
```

**Helper functions (private, module-level):**
- `_extract_negation_words(text: str) -> Set[str]` — returns set of negation/action words found.
- `_negation_match(a: str, b: str) -> bool` — True if both have same negation status (both have negation or neither does).
- `_extract_numbers(text: str) -> Set[str]` — regex extraction.
- `_numbers_match(a: str, b: str) -> bool` — compare number sets.
- `_extract_dates(text: str) -> Set[str]` — regex extraction.
- `_dates_match(a: str, b: str) -> bool` — compare date sets.

### 2.3 `backend/guardrails/factory.py`

```python
def get_guardrail_arbiter() -> GuardrailArbiter: ...
def set_guardrail_arbiter(arbiter: GuardrailArbiter) -> None: ...
```

### 2.4 `backend/guardrails/volatility.py`

**Purpose:** Dynamic TTL classification based on query intent (Section 5.6 spec).

**Classification rules (regex-based):**
- **Volatile** (TTL=0s or 300s): regex patterns for `stock price`, `weather`, `today`, `latest`, `now`, `current time`, `news`.
- **Semi-static** (TTL=24h): `code snippet`, `translation`, `summary`, `explain`, `how to`.
- **Evergreen** (TTL=30d): `math theorem`, `grammar rule`, `definition`, `what is`.

**Interface:**
```python
@dataclass(frozen=True)
class VolatilityClassification:
    category: Literal["volatile", "semi-static", "evergreen"]
    ttl_seconds: int
    confidence: float

class VolatilityEngine:
    def classify(self, text: str) -> VolatilityClassification: ...
```

**Factory functions:**
- `get_volatility_engine() -> VolatilityEngine`
- `set_volatility_engine(engine: VolatilityEngine) -> None`

---

## Sub-Project 3: `backend/semantic/` — `cache_service.py`

**Purpose:** The orchestration layer that ties embedding + vector index + guardrails + volatility together, and plugs into `chat.py`.

```python
class SemanticCacheService:
    """
    Orchestrates the L2 semantic cache lookup flow.
    Called from backend/api/v1/chat.py after L1 miss.
    """

    async def try_semantic_hit(
        self,
        norm_req: NormalizedInferenceRequest,
        tenant_id: str,
        project_id: str,
        incoming_text: str,
    ) -> Optional[SemanticCacheHitResult]:
        """
        Returns a hit result if found AND guardrails pass, else None.
        """
        # 1. Compute scope hash
        system_prompt = extract_system_prompt(norm_req)
        scope_hash = compute_scope_hash(tenant_id, project_id, norm_req.model, system_prompt)

        # 2. Generate embedding (sub-3ms after warmup)
        query_vector = await self._embedding_engine.embed(incoming_text)

        # 3. Search vector index within scope
        candidates = await self._vector_index.search(query_vector, scope_hash, top_k=5)
        if not candidates:
            return None

        # 4. Evaluate top candidate through guardrails
        top_candidate = candidates[0]
        if top_candidate.similarity < 0.92:
            return None

        decision = await self._guardrail_arbiter.evaluate(
            incoming_text=incoming_text,
            candidate_text=self._extract_text_from_payload(top_candidate.response_payload),
            incoming_system_prompt=system_prompt or "",
            candidate_system_prompt=top_candidate.system_prompt,
        )
        if not decision.passed:
            return None

        # 5. Apply dynamic TTL (volatility-based) — already baked into CachedResponse.ttl_seconds
        #    (volatility determines TTL when storing, not at lookup time)

        return SemanticCacheHitResult(
            exact_request_hash=top_candidate.exact_request_hash,
            similarity=top_candidate.similarity,
            response_payload=top_candidate.response_payload,
        )

    async def store_semantic_entry(
        self,
        norm_req: NormalizedInferenceRequest,
        scope_hash: str,
        exact_request_hash: str,
        response_payload: Dict[str, Any],
        cached_response: CachedResponse,
    ) -> None:
        """Called from chat.py on upstream miss to backfill L2."""
        system_prompt = extract_system_prompt(norm_req)
        incoming_text = self._extract_text(norm_req)
        vector = await self._embedding_engine.embed(incoming_text)
        entry = SemanticCacheEntry(...)
        await self._vector_index.insert(scope_hash, entry)
```

**Factory:**
- `get_semantic_cache_service() -> SemanticCacheService`
- `set_semantic_cache_service(svc: SemanticCacheService) -> None`

---

## Sub-Project 4: Modify `backend/api/v1/chat.py`

Insert the L2 flow between L1 miss and upstream call:

```python
# ... existing L1 lookup code unchanged ...

if cached is not None:
    # EXACT HIT (unchanged)
    ...

# 4. L1 MISS → Try L2 Semantic Cache
semantic_service = get_semantic_cache_service()
incoming_text = OpenAIAdapter.extract_last_user_message(norm_req)  # NEW helper needed
semantic_hit = await semantic_service.try_semantic_hit(
    norm_req=norm_req,
    tenant_id=identity.tenant_id,
    project_id=identity.project_id,
    incoming_text=incoming_text,
)

if semantic_hit is not None:
    # SEMANTIC HIT (guardrails passed)
    cache_status = "SEMANTIC_HIT"
    upstream_called = False
    upstream_latency_ms = None
    response_body = OpenAIAdapter.format_cached_response(
        semantic_hit.response_payload, request_id, norm_req.model
    )
    gateway_latency_ms = ...
    # Telemetry with cache_status="SEMANTIC_HIT"
    headers = {
        "X-CacheMind-Status": "SEMANTIC_HIT",
        "X-CacheMind-Request-ID": request_id,
        "X-CacheMind-Exact-Hash": semantic_hit.exact_request_hash,
        "X-CacheMind-Gateway-Latency-Ms": f"{gateway_latency_ms:.3f}",
        "X-CacheMind-Lookup-Ms": f"{semantic_lookup_ms:.3f}",
    }
    return JSONResponse(content=response_body, headers=headers)

# 5. CACHE MISS → Forward to upstream provider (existing code, unchanged)
# ... rest of file unchanged ...
# But AFTER upstream success, add L2 backfill:
# await semantic_service.store_semantic_entry(norm_req, scope_hash, exact_request_hash, provider_resp.raw_response, cached_entry)
```

**New helper needed in `backend/normalization/openai_adapter.py`:**
```python
@staticmethod
def extract_last_user_message(norm_req: NormalizedInferenceRequest) -> str:
    """Returns the text of the last user message for semantic embedding."""
    for msg in reversed(norm_req.messages):
        if msg.role == "user" and isinstance(msg.content, str):
            return msg.content
    return ""

@staticmethod
def format_cached_response(payload: Dict[str, Any], request_id: str, model: str) -> Dict[str, Any]:
    """Formats a cached payload into the standard OpenAI chat completion response shape."""
    ...  # already exists in Phase 1
```

---

## Sub-Project 5: Update DB Models for L2 Telemetry

### 5.1 `backend/db/models.py` changes

Add new columns to `RequestLog` to capture semantic-specific metadata:

```python
class RequestLog(Base):
    # ... existing columns unchanged ...

    # NEW: L2 semantic metadata
    similarity_score = Column(Float, nullable=True)       # cosine similarity of L2 hit
    guardrail_reason = Column(String(128), nullable=True) # e.g., "PASS", "FAIL: negation"
```

### 5.2 `backend/db/repositories.py` changes

Update `RequestLogRepository.create_log()` to accept the new optional fields.

### 5.3 `backend/telemetry/service.py` changes

Update `TelemetryService.record_request_log()` signature to accept `similarity_score` and `guardrail_reason`.

---

## Sub-Project 6: `pyproject.toml` Dependency Updates

```toml
[dependencies]
# ... existing unchanged ...
fastembed = "^0.3.0"       # local ONNX embeddings
numpy = "^1.26.0"          # vector math
hnswlib = "^1.7.3"         # HNSW vector index (best-effort; fallback to numpy if unavailable)
```

**Note:** `hnswlib` can be tricky to compile on Windows. Plan B: if install fails, implement `numpy`-based cosine search in `VectorIndex` with O(N) scan, which is acceptable for <10k entries. The spec says "HNSW/Cosine" — cosine is the algorithm, HNSW is one implementation option.

---

## Sub-Project 7: Phase 2 Tests

### 7.1 New file: `backend/tests/unit/test_semantic_embedding.py`

Tests for `EmbeddingEngine`:
- `test_embedding_dimensionality()` — verify 384-dim output.
- `test_embedding_determinism()` — same text → same vector (within tolerance).
- `test_embedding_latency()` — warmup call < 50ms (Cold start may be slow, but warmup must be < 3ms per spec).
- `test_embedding_semantic_similarity()` — "How do I bake bread?" vs "Recipe for sourdough" → similarity > 0.85.

### 7.2 New file: `backend/tests/unit/test_guardrail_arbiter.py`

Tests for `GuardrailArbiter`:
- `test_negation_reject()` — "Cancel my order" vs "Renew my order" → REJECT.
- `test_number_reject()` — "Refund $50" vs "Refund $500" → REJECT.
- `test_date_reject()` — "Meeting on 2024-01-01" vs "Meeting on 2025-01-01" → REJECT.
- `test_system_prompt_mismatch_reject()` — different system prompts → REJECT.
- `test_passing_match()` — identical queries → PASS.
- `test_passing_similar()` — "What is the capital of France?" vs "What's the capital of France?" → PASS (same numbers/dates/negations).

### 7.3 New file: `backend/tests/unit/test_volatility_engine.py`

Tests for `VolatilityEngine`:
- `test_volatile_stock_price()` → category="volatile", ttl=0 or 300.
- `test_volatile_weather_today()` → category="volatile".
- `test_semi_static_code_snippet()` → category="semi-static", ttl=86400.
- `test_evergreen_math_theorem()` → category="evergreen", ttl=2592000.

### 7.4 New file: `backend/tests/integration/test_semantic_cache_flow.py`

End-to-end tests (matching the pattern of `test_exact_cache_flow.py`):
- `test_semantic_cache_hit_and_zero_upstream_calls()` — two queries with similar phrasing but different wording → L2 HIT, `call_count == 1`.
- `test_semantic_cache_negation_reject()` — "Cancel my order" vs "Renew my order" → L2 MISS (guardrail rejects), `call_count == 2`.
- `test_semantic_cache_number_reject()` — "Refund $50" vs "Refund $500" → L2 MISS, `call_count == 2`.
- `test_semantic_cache_system_prompt_isolation()` — same text, different system prompt → no L2 hit (scope hash separates namespaces).
- `test_semantic_cache_telemetry_logging()` — verify `similarity_score` and `guardrail_reason` in `RequestLog`.
- `test_semantic_hit_response_headers()` — verify `X-CacheMind-Status: SEMANTIC_HIT` and `X-CacheMind-Lookup-Ms`.

### 7.5 Update `backend/tests/conftest.py`

Add fixtures for Phase 2 test doubles:
```python
@pytest_asyncio.fixture(scope="function")
def semantic_fixtures():
    """Provides embedding_engine, vector_index, guardrail_arbiter, volatility_engine, semantic_service."""
    # Inject test doubles via set_* functions
    ...
```

### 7.6 New file: `backend/tests/integration/test_semantic_isolation.py`

- `test_cross_tenant_semantic_isolation()` — Tenant A's semantic hit must never leak to Tenant B (different scope hashes).
- `test_cross_model_semantic_isolation()` — Same text, different model → no semantic hit.

---

## Implementation Order & Estimated Sessions

| Session | Deliverable | Tests |
|---|---|---|
| **S1** | `semantic/` package: `__init__.py`, `embedding.py`, `models.py`, `backend.py`, `factory.py` | `test_semantic_embedding.py` (unit) |
| **S2** | `semantic/vector_index.py` — HNSW or numpy fallback | `test_semantic_embedding.py` — vector search tests |
| **S3** | `guardrails/` package: `arbiter.py`, `volatility.py`, `factory.py` | `test_guardrail_arbiter.py`, `test_volatility_engine.py` (unit) |
| **S4** | `semantic/cache_service.py` — orchestration layer | — |
| **S5** | Modify `chat.py`, `openai_adapter.py`, `db/models.py`, `repositories.py`, `telemetry/service.py` | — |
| **S6** | `pyproject.toml` dependency updates; install & verify FastEmbed ONNX loads | — |
| **S7** | Integration tests: `test_semantic_cache_flow.py`, `test_semantic_isolation.py`, update `conftest.py` | All integration tests |
| **S8** | End-to-end verification: run full `pytest backend/tests/` (target: 20 + new tests all passing) | Full suite |

**Total: 8 sessions** (mirrors the spec's Week 3 + Week 4 learning curriculum).

---

## Critical Design Constraints (Must Not Break Phase 1)

1. **`ExactCacheBackend` protocol unchanged** — no existing method signatures modified.
2. **`get_cache_backend()` singleton pattern preserved** — new singletons use the same `set_*` injection pattern for tests.
3. **`chat.py` exact hit path unchanged** — L1 EXACT_HIT logic is untouched; L2 only triggers on L1 MISS.
4. **`MockProvider.call_count` still the truth** — any semantic hit must NOT increment `call_count`.
5. **All new test doubles injectable via `set_*` functions** — conftest fixtures must isolate each test.
6. **`RequestLog` schema backward-compatible** — new columns nullable; existing seed data unaffected.
7. **FastEmbed model loading must be async-safe** — `EmbeddingEngine.__init__` must not block the event loop; model load happens lazily or in startup hook.

---

## Verification Checklist (Phase 2 Done)

- [ ] `pytest backend/tests/` passes all Phase 1 tests (20/20 unchanged).
- [ ] All new unit tests pass (embedding, guardrail, volatility).
- [ ] All new integration tests pass (semantic hit, negation reject, number reject, isolation).
- [ ] `X-CacheMind-Status: SEMANTIC_HIT` header returned on semantic hits.
- [ ] `X-CacheMind-Status: MISS` still returned when guardrails reject.
- [ ] `provider.call_count` unchanged on semantic hits (zero upstream calls).
- [ ] `similarity_score` and `guardrail_reason` columns populated in `RequestLog` on semantic hits.
- [ ] Cross-tenant and cross-model isolation verified.
- [ ] FastEmbed ONNX model loads and produces 384-dim vectors in < 3ms (warmup).
- [ ] `hnswlib` installed and HNSW search confirmed; numpy fallback documented if install fails.
