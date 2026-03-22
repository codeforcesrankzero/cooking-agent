"""Main pipeline: user query → search → LLM → response."""

import asyncio
import logging
import re

from src.config import settings
from src.db.logs import write_log
from src.db.prices import get_prices
from src.db.recipes import search_by_ingredients
from src.llm.client import generate_response
from src.search.semantic import search_semantic
from src.services.session import session_manager

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset(
    "и в на из за по с у о к до от что как это мне для нет да есть хочу можно нужно"
    " бы не ещё еще тоже уже очень всё все какой какая какое какие".split()
)

_COMPOUND_PATTERN = re.compile(
    r"(куриная\s+грудка|куриное\s+филе|говяжий\s+фарш|свиной\s+фарш"
    r"|соевый\s+соус|сливочное\s+масло|оливковое\s+масло|растительное\s+масло"
    r"|томатная\s+паста|болгарский\s+перец|зелёный\s+лук|зеленый\s+лук"
    r"|сметана|кокосовое\s+молоко|грецкие\s+орехи|лавровый\s+лист"
    r"|чёрный\s+перец|черный\s+перец|бальзамический\s+уксус)",
    re.IGNORECASE,
)


def _extract_ingredients(text: str) -> list[str]:
    """Extract ingredient terms from user message."""
    found_compounds = _COMPOUND_PATTERN.findall(text)
    remaining = _COMPOUND_PATTERN.sub("", text)

    remaining = remaining.replace(",", " ").replace(" и ", " ")
    words = [w.strip().lower() for w in remaining.split() if len(w.strip()) > 2]
    words = [w for w in words if w not in _STOP_WORDS]

    return [c.lower().strip() for c in found_compounds] + words


async def process_query(user_message: str, chat_id: int) -> str:
    """Run the full pipeline for a user message."""
    session = session_manager.get(chat_id)
    session.add_message("user", user_message)

    try:
        ingredients = _extract_ingredients(user_message)

        fts_task = search_by_ingredients(ingredients) if ingredients else asyncio.sleep(0)
        sem_task = search_semantic(user_message)
        results = await asyncio.gather(fts_task, sem_task, return_exceptions=True)

        fts_results = results[0] if isinstance(results[0], list) else []
        semantic_results = results[1] if isinstance(results[1], list) else []

        combined = _combine_results(fts_results, semantic_results)

        if combined and combined[0].get("score", 0) >= settings.direct_answer_threshold:
            top_recipes = combined[:3]
            all_ingredients: list[str] = []
            for recipe in top_recipes:
                all_ingredients.extend(recipe.get("ingredients", []))
            prices = await get_prices(list(set(all_ingredients))) if all_ingredients else {}
            response = _format_direct_response(top_recipes, prices)
        else:
            recipes_text = _format_recipes(combined)
            all_ingredients = []
            for recipe in combined:
                all_ingredients.extend(recipe.get("ingredients", []))
            prices = await get_prices(list(set(all_ingredients))) if all_ingredients else {}
            prices_text = _format_prices(prices)
            history = session.get_history_text()
            response = await generate_response(recipes_text, prices_text, history, user_message)

    except Exception:
        logger.exception("Pipeline error for chat_id=%s", chat_id)
        response = "Произошла ошибка при обработке запроса. Попробуйте ещё раз."

    session.add_message("assistant", response)
    await write_log(chat_id, user_message, response)
    return response


def _combine_results(fts_results: list[dict], semantic_results: list[dict]) -> list[dict]:
    """Merge FTS5 and semantic results, deduplicate, rank by score, return top-N."""
    by_id: dict[int | str, dict] = {}

    for recipe in fts_results + semantic_results:
        rid = recipe.get("id")
        if rid in by_id:
            existing = by_id[rid]
            if recipe.get("score", 0) > existing.get("score", 0):
                existing["score"] = recipe["score"]
            if recipe.get("source") != existing.get("source"):
                existing["source"] = "both"
        else:
            by_id[rid] = recipe

    ranked = sorted(by_id.values(), key=lambda r: r.get("score", 0), reverse=True)

    threshold = settings.relevance_threshold
    ranked = [r for r in ranked if r.get("score", 0) >= threshold]

    return ranked[: settings.search_top_n]


_NUM_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def _difficulty_label(steps_count: int, minutes: int | None) -> str:
    mins = minutes or 0
    if steps_count <= 5 and mins <= 20:
        return "Просто"
    if steps_count <= 10 or mins <= 45:
        return "Средне"
    return "Сложно"


def _format_direct_response(recipes: list[dict], prices: dict[str, float | None]) -> str:
    """Format structured recipe cards for Telegram (Markdown v1)."""
    header = f"🍽 *Нашёл {len(recipes)} {_plural_recipe(len(recipes))}:*\n"
    parts = [header]

    for i, r in enumerate(recipes, 1):
        name = r.get("name", "Без названия")
        minutes = r.get("minutes")
        tags = r.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        ingredients = r.get("ingredients", [])
        if isinstance(ingredients, str):
            ingredients = [ingredients]

        steps = r.get("steps", [])
        if isinstance(steps, str):
            steps = [steps]

        difficulty = _difficulty_label(len(steps), minutes)
        num = _NUM_EMOJI.get(i, f"{i}.")

        time_str = f"⏱ {minutes} мин" if minutes else ""
        meta_parts = [s for s in [time_str, f"📊 {difficulty}"] if s]
        meta_line = " · ".join(meta_parts)

        ing_lines = "\n".join(f"  • {ing}" for ing in ingredients)

        step_lines = "\n".join(
            f"  {j}. {s}" for j, s in enumerate(steps[:6], 1)
        )
        if len(steps) > 6:
            step_lines += f"\n  _...ещё {len(steps) - 6} шагов_"

        known_prices = []
        total = 0.0
        for ing in ingredients:
            p = prices.get(ing)
            if p is not None:
                known_prices.append(f"  • {ing} — ~{p:.0f} руб.")
                total += p

        price_block = ""
        if known_prices:
            price_block = (
                "\n\n💰 *Цены на ингредиенты:*\n"
                + "\n".join(known_prices)
                + f"\n  ≈ Итого: ~{total:.0f} руб."
            )

        tag_line = ""
        if tags:
            visible_tags = tags[:5]
            tag_line = "\n🏷 " + " · ".join(visible_tags)

        card = (
            f"{num} *{name}*\n"
            f"{meta_line}\n\n"
            f"🥘 *Ингредиенты:*\n{ing_lines}\n\n"
            f"📝 *Приготовление:*\n{step_lines}"
            f"{price_block}"
            f"{tag_line}"
        )
        parts.append(card)

    return "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(parts)


def _plural_recipe(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "рецепт"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "рецепта"
    return "рецептов"


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
