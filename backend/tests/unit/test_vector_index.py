import pytest
import numpy as np

from backend.semantic.vector_index import VectorIndex, SemanticCandidate


@pytest.mark.asyncio
async def test_vector_index_insert_and_search_within_scope():
    index = VectorIndex(dim=384, threshold=0.90)
    await index.clear()

    scope_1 = "scope_alpha"
    scope_2 = "scope_beta"

    vec_a = [1.0] + [0.0] * 383
    vec_similar = [0.98] + [0.198997] + [0.0] * 382  # cosine sim ~ 0.98

    # Insert into scope 1
    await index.insert(
        scope_hash=scope_1,
        exact_request_hash="exact_1",
        vector=vec_a,
        response_payload={"choices": [{"message": {"content": "Answer 1"}}]},
        created_at=1000.0,
    )

    # Search in scope 1
    results = await index.search(vec_similar, scope_hash=scope_1, top_k=5)
    assert len(results) == 1
    assert results[0].exact_request_hash == "exact_1"
    assert results[0].similarity > 0.95
    assert results[0].response_payload["choices"][0]["message"]["content"] == "Answer 1"

    # Search in scope 2 (should find nothing due to namespace isolation)
    results_scope2 = await index.search(vec_similar, scope_hash=scope_2, top_k=5)
    assert len(results_scope2) == 0


@pytest.mark.asyncio
async def test_vector_index_threshold_filter():
    index = VectorIndex(dim=384, threshold=0.95)
    await index.clear()

    scope = "scope_test"
    vec_a = [1.0] + [0.0] * 383
    vec_low_sim = [0.7071] + [0.7071] + [0.0] * 382  # sim ~ 0.707

    await index.insert(
        scope_hash=scope,
        exact_request_hash="exact_low",
        vector=vec_a,
        response_payload={"data": "test"},
        created_at=1000.0,
    )

    # Search with low similarity vector
    results = await index.search(vec_low_sim, scope_hash=scope, top_k=5)
    assert len(results) == 0  # Filtered out by 0.95 threshold


@pytest.mark.asyncio
async def test_vector_index_delete():
    index = VectorIndex(dim=384, threshold=0.90)
    await index.clear()

    scope = "scope_del"
    vec = [1.0] + [0.0] * 383

    await index.insert(
        scope_hash=scope,
        exact_request_hash="exact_del_me",
        vector=vec,
        response_payload={"data": "to delete"},
        created_at=1000.0,
    )

    res = await index.search(vec, scope_hash=scope)
    assert len(res) == 1

    deleted = await index.delete("exact_del_me")
    assert deleted is True

    res_after = await index.search(vec, scope_hash=scope)
    assert len(res_after) == 0
