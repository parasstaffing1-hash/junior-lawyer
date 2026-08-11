from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.services.search_index.engine import feature_vector


@lru_cache(maxsize=1)
def _local_sentence_transformer():
    path = settings.search_local_embedding_model_path
    if not path:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # optional, deliberately not a base dependency
        return SentenceTransformer(path, local_files_only=True)
    except Exception:
        return None


def local_embedding(text: str, *, expand_legal: bool = True) -> list[float]:
    """Return a zero-cost local vector.

    If SEARCH_LOCAL_EMBEDDING_MODEL_PATH points to an already-downloaded sentence-transformers
    model, it is used entirely locally. Otherwise the deterministic feature-hash vector is used.
    No remote embedding service is contacted by this function.
    """
    model = _local_sentence_transformer()
    if model is None:
        return feature_vector(text, expand_legal=expand_legal)
    vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
    return [round(float(value), 7) for value in vector.tolist()]
