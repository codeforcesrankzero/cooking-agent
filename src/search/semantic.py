"""Semantic search over recipes using ChromaDB."""

import asyncio
import logging

import chromadb

from src.config import settings
from src.search.embedding import get_embedding_function

logger = logging.getLogger(__name__)

_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection | None:
    global _collection
    if _collection is None:
        try:
            client = chromadb.PersistentClient(path=settings.chroma_path)
            _collection = client.get_or_create_collection(
                name="recipes",
                metadata={"hnsw:space": "cosine"},
                embedding_function=get_embedding_function(),
            )
            if _collection.count() == 0:
                logger.warning("ChromaDB collection 'recipes' is empty")
                return None
        except Exception:
            logger.exception("Failed to connect to ChromaDB")
            return None
    return _collection


def _query_sync(query: str, n: int) -> dict | None:
    """Run ChromaDB query synchronously (called from thread pool)."""
    collection = _get_collection()
    if collection is None:
        return None
    try:
        return collection.query(query_texts=[query], n_results=n)
    except Exception:
        logger.exception("ChromaDB query failed")
        return None


async def search_semantic(query: str, top_n: int | None = None) -> list[dict]:
    """Search recipes by semantic similarity. Returns results with score and source."""
    collection = _get_collection()
    if collection is None:
        return []

    n = min(top_n or settings.search_top_n, collection.count())
    if n == 0:
        return []

    results = await asyncio.to_thread(_query_sync, query, n)

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    raw = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i] if results["distances"] else 1.0
        raw.append({
            "id": int(results["ids"][0][i]),
            "distance": distance,
            "score": max(0.0, 1.0 - distance),
            "source": "semantic",
        })

    from src.db.recipes import get_recipes_by_ids

    ids = [r["id"] for r in raw]
    full_recipes = await get_recipes_by_ids(ids)
    by_id = {r["id"]: r for r in full_recipes}

    enriched = []
    for r in raw:
        full = by_id.get(r["id"])
        if full:
            full["score"] = r["score"]
            full["distance"] = r["distance"]
            full["source"] = r["source"]
            enriched.append(full)

    return enriched
