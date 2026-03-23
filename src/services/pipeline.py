"""Main pipeline: user query → search → LLM → response."""

import asyncio
import logging
import time

from src.config import settings
from src.db.logs import write_log
from src.db.prices import get_prices
from src.db.recipes import search_by_ingredients
from src.llm.client import generate_response, translate_to_english
from src.search.semantic import search_semantic
from src.services.session import session_manager

logger = logging.getLogger(__name__)

_EN_STOP = frozenset(
    "i me my we our you your he she it they them the a an and in on at to for "
    "of with from by is are was were be been have has had do does did will "
    "would can could should may might not no or but if so what how want need "
    "like some something anything very much many just also make cook prepare "
    "got there here".split()
)


def _extract_ingredients(text: str) -> list[str]:
    text = text.replace(",", " ").replace(" and ", " ")
    words = [w.strip().lower() for w in text.split() if len(w.strip()) > 2]
    return [w for w in words if w not in _EN_STOP]


async def process_query(user_message: str, chat_id: int) -> str:
    t0 = time.perf_counter()
    session = session_manager.get(chat_id)
    session.add_message("user", user_message)

    try:
        en_query = await translate_to_english(user_message)
        logger.debug("translated query: %r -> %r", user_message, en_query)

        ingredients = _extract_ingredients(en_query)

        ts = time.perf_counter()
        fts_task = search_by_ingredients(ingredients) if ingredients else asyncio.sleep(0)
        sem_task = search_semantic(en_query)
        results = await asyncio.gather(fts_task, sem_task, return_exceptions=True)
        logger.debug("search took %.3fs", time.perf_counter() - ts)

        fts_results = results[0] if isinstance(results[0], list) else []
        semantic_results = results[1] if isinstance(results[1], list) else []

        logger.debug(
            "search fts=%d semantic=%d | fts_top=%s | sem_top=%s",
            len(fts_results),
            len(semantic_results),
            [(r.get("name", "")[:30], round(r.get("score", 0), 3)) for r in fts_results[:5]],
            [(r.get("name", "")[:30], round(r.get("score", 0), 3)) for r in semantic_results[:5]],
        )

        combined = _combine_results(fts_results, semantic_results)

        recipes_text = _format_recipes(combined)
        all_ingredients: list[str] = []
        for recipe in combined:
            all_ingredients.extend(recipe.get("ingredients", []))
        tp = time.perf_counter()
        prices = await get_prices(list(set(all_ingredients))) if all_ingredients else {}
        logger.debug("prices took %.3fs", time.perf_counter() - tp)
        prices_text = _format_prices(prices)
        history = session.get_history_text()
        tl = time.perf_counter()
        response = await generate_response(recipes_text, prices_text, history, user_message)
        logger.debug("llm took %.3fs", time.perf_counter() - tl)

    except Exception:
        logger.exception("Pipeline error for chat_id=%s", chat_id)
        response = "Произошла ошибка при обработке запроса. Попробуйте ещё раз."
        session.add_message("assistant", response)
        return response

    logger.debug("total pipeline %.3fs", time.perf_counter() - t0)
    session.add_message("assistant", response)
    await write_log(chat_id, user_message, response)
    return response


def _combine_results(fts_results: list[dict], semantic_results: list[dict]) -> list[dict]:
    by_id: dict[int | str, dict] = {}

    for recipe in fts_results:
        rid = recipe.get("id")
        by_id[rid] = {**recipe, "fts_score": recipe.get("score", 0), "semantic_score": 0.0}

    for recipe in semantic_results:
        rid = recipe.get("id")
        sem_score = recipe.get("score", 0)
        if rid in by_id:
            by_id[rid]["semantic_score"] = sem_score
            by_id[rid]["score"] = max(by_id[rid]["fts_score"], sem_score)
            by_id[rid]["source"] = "both"
        else:
            by_id[rid] = {**recipe, "fts_score": 0.0, "semantic_score": sem_score}

    threshold = settings.relevance_threshold
    ranked = [
        r for r in by_id.values()
        if r["fts_score"] >= threshold or r["semantic_score"] >= threshold
    ]
    ranked.sort(key=lambda r: r.get("score", 0), reverse=True)
    return ranked[: settings.search_top_n]


def _format_recipes(recipes: list[dict]) -> str:
    if not recipes:
        return ""
    parts = []
    for i, r in enumerate(recipes, 1):
        ingredients = r.get("ingredients", [])
        if isinstance(ingredients, list):
            ingredients = ", ".join(ingredients)
        steps = r.get("steps", [])
        if isinstance(steps, list):
            steps = " → ".join(steps[:5])
            if len(r.get("steps", [])) > 5:
                steps += " → ..."
        parts.append(
            f"{i}. {r.get('name', 'Без названия')}\n"
            f"   Ингредиенты: {ingredients}\n"
            f"   Шаги: {steps}\n"
            f"   Время: {r.get('minutes', '?')} мин"
        )
    return "\n\n".join(parts)


def _format_prices(prices: dict[str, float | None]) -> str:
    if not prices:
        return ""
    lines = [f"- {p}: {v:.0f} руб." for p, v in sorted(prices.items()) if v is not None]
    return "\n".join(lines)
