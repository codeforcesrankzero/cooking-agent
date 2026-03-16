"""Multilingual embedding function for ChromaDB."""

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embedding_model)
    return _model


class MultilingualEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        model = _get_model()
        embeddings = model.encode(input, normalize_embeddings=True)
        return embeddings.tolist()


def get_embedding_function() -> MultilingualEmbeddingFunction:
    return MultilingualEmbeddingFunction()


def preload_model() -> None:
    """Eagerly load the SentenceTransformer model (call at app startup)."""
    _get_model()
