import pytest
import numpy as np

from backend.semantic.embedding import MockEmbeddingEngine, EmbeddingEngine, FASTEMBED_AVAILABLE


@pytest.mark.asyncio
async def test_mock_embedding_engine_deterministic():
    engine = MockEmbeddingEngine(dim=384)
    vec1 = await engine.embed("What is the speed of light?")
    vec2 = await engine.embed("What is the speed of light?")
    vec3 = await engine.embed("How to make a cup of tea?")

    assert len(vec1) == 384
    assert len(vec2) == 384
    assert vec1 == vec2
    assert vec1 != vec3

    # Verify unit norm
    norm = np.linalg.norm(np.array(vec1))
    assert pytest.approx(norm, rel=1e-5) == 1.0


@pytest.mark.asyncio
async def test_mock_embedding_batch():
    engine = MockEmbeddingEngine(dim=384)
    texts = ["hello world", "test query 1", "test query 2"]
    vecs = await engine.embed_batch(texts)

    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == 384
        assert pytest.approx(np.linalg.norm(np.array(v)), rel=1e-5) == 1.0


@pytest.mark.asyncio
async def test_embedding_engine_properties():
    engine = MockEmbeddingEngine(dim=384)
    assert engine.embedding_dim == 384
    assert engine.model_name == "mock-embedding"


@pytest.mark.asyncio
async def test_mock_embedding_register_similar():
    engine = MockEmbeddingEngine(dim=384)
    t1 = "What is the capital of France?"
    t2 = "Tell me the capital of France"

    engine.register_similar(t1, t2, similarity=0.96)
    v1 = await engine.embed(t1)
    v2 = await engine.embed(t2)

    cos_sim = float(np.dot(np.array(v1), np.array(v2)))
    assert pytest.approx(cos_sim, abs=1e-4) == 0.96

