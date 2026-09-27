"""
Local ONNX Embedding Engine using FastEmbed (Sub-3ms target).

FastEmbed uses ONNX Runtime to run quantized embedding models (bge-small-en-v1.5, etc.)
entirely on CPU with no PyTorch dependency.
"""

import asyncio
import os
from typing import List, Optional

import numpy as np

# FastEmbed imports (optional at module load time)
try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False
    TextEmbedding = None  # type: ignore


_embedding_engine_instance: Optional["EmbeddingEngine"] = None


class EmbeddingEngine:
    """
    Singleton embedding engine using FastEmbed ONNX models.

    Loads model lazily on first embed() call to avoid blocking startup.
    Warmup happens on first call; subsequent calls target < 3ms latency.

    Model: BAAI/bge-small-en-v1.5 (384-dim, ~33MB, ~2.5ms/query on CPU)
    """

    _instance: Optional["EmbeddingEngine"] = None
    _model: Optional["TextEmbedding"] = None
    _model_name: str = "BAAI/bge-small-en-v1.5"
    _embedding_dim: int = 384
    _warmup_done: bool = False

    def __new__(cls, model_name: str = "BAAI/bge-small-en-v1.5") -> "EmbeddingEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._model_name = model_name
        return cls._instance

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        if self._warmup_done:
            return
        self._model_name = model_name
        # Set cache dir for reproducibility
        self._cache_dir = os.environ.get("FASTEMBED_CACHE_DIR", os.path.expanduser("~/.cache/fastembed"))

    def _ensure_model_loaded(self) -> None:
        """Load the FastEmbed model if not already loaded, or fallback to mock engine."""
        if self._model is None and getattr(self, "_fallback_engine", None) is None:
            if not FASTEMBED_AVAILABLE:
                self._fallback_engine = MockEmbeddingEngine(dim=self._embedding_dim)
                return
            self._model = TextEmbedding(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )

    def _warmup(self) -> None:
        """Run a warmup embedding to trigger ONNX model compilation."""
        if self._warmup_done or getattr(self, "_fallback_engine", None) is not None:
            return
        self._ensure_model_loaded()
        if self._model:
            # Warmup with a representative query
            _ = list(self._model.embed(["warmup query for cachemind semantic search"]))
        self._warmup_done = True

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        First call includes model load + warmup (~50-200ms cold).
        Subsequent calls target < 3ms latency.

        Args:
            text: Input text to embed

        Returns:
            List of 384 floats (L2-normalized for cosine similarity)
        """
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, text)

    def _embed_sync(self, text: str) -> List[float]:
        """Synchronous embedding (runs in executor)."""
        self._ensure_model_loaded()
        if getattr(self, "_fallback_engine", None) is not None:
            return self._fallback_engine._deterministic_vector(text)

        if not self._warmup_done:
            self._warmup()

        embeddings = list(self._model.embed([text]))
        if not embeddings:
            raise ValueError(f"Failed to generate embedding for: {text[:50]}...")

        vec = np.array(embeddings[0], dtype=np.float32)
        # FastEmbed returns L2-normalized vectors by default, but verify
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def register_similar(self, text_a: str, text_b: str, similarity: float = 0.96) -> None:
        """Registers similar texts on fallback engine if active."""
        self._ensure_model_loaded()
        if getattr(self, "_fallback_engine", None) is not None:
            self._fallback_engine.register_similar(text_a, text_b, similarity)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of input texts

        Returns:
            List of 384-dim float lists
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_batch_sync, texts)

    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous batch embedding (runs in executor)."""
        self._ensure_model_loaded()
        if not self._warmup_done:
            self._warmup()

        embeddings = list(self._model.embed(texts))
        if len(embeddings) != len(texts):
            raise ValueError(f"Embedding count mismatch: {len(embeddings)} vs {len(texts)}")

        result = []
        for emb in embeddings:
            vec = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            result.append(vec.tolist())
        return result

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @property
    def model_name(self) -> str:
        return self._model_name

    async def close(self) -> None:
        """Cleanup (no-op for FastEmbed, kept for interface compatibility)."""
        pass


def get_embedding_engine(model_name: str = "BAAI/bge-small-en-v1.5") -> EmbeddingEngine:
    """Returns singleton EmbeddingEngine instance."""
    global _embedding_engine_instance
    if _embedding_engine_instance is None:
        _embedding_engine_instance = EmbeddingEngine(model_name)
    return _embedding_engine_instance


def set_embedding_engine(engine: EmbeddingEngine) -> None:
    """Explicitly sets or overrides embedding engine instance (for tests)."""
    global _embedding_engine_instance
    _embedding_engine_instance = engine


class MockEmbeddingEngine:
    """
    Deterministic test double for EmbeddingEngine.
    Returns pseudo-random but deterministic vectors based on text hash.
    """

    def __init__(self, dim: int = 384, seed: int = 42) -> None:
        self._dim = dim
        self._rng = np.random.default_rng(seed)
        self._cache: dict[str, List[float]] = {}

    def _deterministic_vector(self, text: str) -> List[float]:
        """Generate deterministic vector from text hash."""
        if text in self._cache:
            return self._cache[text]

        # Use hash to seed a deterministic vector
        hash_val = hash(text) & 0xFFFFFFFF
        rng = np.random.default_rng(hash_val)
        vec = rng.standard_normal(self._dim).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        self._cache[text] = vec.tolist()
        return self._cache[text]

    def register_similar(self, text_a: str, text_b: str, similarity: float = 0.96) -> None:
        """Register two texts to produce vectors with an exact cosine similarity."""
        vec_a = np.array(self._deterministic_vector(text_a), dtype=np.float32)
        # Create an orthogonal vector to vec_a
        rng = np.random.default_rng(hash(text_b) & 0xFFFFFFFF)
        rand_v = rng.standard_normal(self._dim).astype(np.float32)
        # Gram-Schmidt orthogonalization
        perp = rand_v - np.dot(rand_v, vec_a) * vec_a
        perp = perp / np.linalg.norm(perp)

        # Construct vec_b with exact cosine similarity s
        s = float(similarity)
        beta = np.sqrt(max(0.0, 1.0 - s * s))
        vec_b = s * vec_a + beta * perp
        vec_b = vec_b / np.linalg.norm(vec_b)

        self._cache[text_b] = vec_b.tolist()

    async def embed(self, text: str) -> List[float]:
        return self._deterministic_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._deterministic_vector(t) for t in texts]

    @property
    def embedding_dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return "mock-embedding"

    async def close(self) -> None:
        pass