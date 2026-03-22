"""FTS5 search for recipes in SQLite."""

import json
import logging

import aiosqlite

from src.config import settings

logger = logging.getLogger(__name__)


async def search_by_ingredients(ingredients: list[str]) -> list[dict]:
    """Search recipes by ingredients using FTS5."""
    if not ingredients:
        return []

    terms = [f'"{term}"' for term in ingredients if term.strip()]
    if not terms:
        return []
    query = " OR ".join(terms)

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT r.id, r.name, r.ingredients, r.steps, r.minutes, r.tags,
                       fts.rank AS fts_rank
                FROM recipes_fts fts
                JOIN recipes r ON fts.rowid = r.id
                WHERE recipes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, settings.search_top_n),
            )
            rows = await cursor.fetchall()
    except Exception:
        logger.exception("FTS5 search failed for query: %s", query)
        return []

    results = []
    for row in rows:
        d = _row_to_dict(row)
        d["score"] = 1.0 / (1.0 + abs(row["fts_rank"]))
        d["source"] = "fts"
        results.append(d)
    return results


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "ingredients": _parse_json(row["ingredients"]),
        "steps": _parse_json(row["steps"]),
        "minutes": row["minutes"],
        "tags": _parse_json(row["tags"]),
    }


async def get_recipes_by_ids(ids: list[int]) -> list[dict]:
    """Fetch full recipe rows by a list of IDs."""
    if not ids:
        return []
    int_ids = [int(i) for i in ids]
    placeholders = ",".join("?" for _ in int_ids)
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT id, name, ingredients, steps, minutes, tags FROM recipes "
                f"WHERE id IN ({placeholders})",
                int_ids,
            )
            rows = await cursor.fetchall()
    except Exception:
        logger.exception("Failed to fetch recipes by IDs: %s", ids)
        return []
    by_id = {row["id"]: _row_to_dict(row) for row in rows}
    return [by_id[i] for i in int_ids if i in by_id]


def _parse_json(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [value]
