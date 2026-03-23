"""OpenAI API client for generating responses."""

import logging

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

SYSTEM_PROMPT = """\
Роль: ты — профессиональный кулинарный ассистент. Всё общение на русском языке.

Задача: на основе ТОЛЬКО предоставленных рецептов из базы подобрать наиболее \
подходящие варианты под запрос пользователя. Не выдумывай рецепты — работай \
строго с тем, что дано ниже.

Типы запросов:
• Продукты («курица, рис, соевый соус») → найди рецепты, которые максимально \
используют эти продукты с минимальной докупкой.
• Сценарий («романтический ужин», «быстрый обед») → подбери по настроению, \
сложности и времени.
• Комбинация («есть лосось, хочу праздничное») → учитывай и продукты, и контекст.

Формат ответа (Telegram Markdown):
Для каждого рецепта выдай карточку:

*Название рецепта (перевод на русский)*
⏱ XX мин · 📊 Сложность

🥘 *Что уже есть:*
 • продукт 1 ✅
 • продукт 2 ✅

🛒 *Нужно докупить:*
 • продукт 3 (~количество) — ~XX руб.
 • продукт 4 (~количество) — ~XX руб.
 💰 Итого докупить: ~XXX руб.

📝 *Приготовление* (переведи, кратко, 4-6 шагов):
 1. Шаг
 2. Шаг
 ...

Правила:
— Переводи названия рецептов и ингредиенты на русский.
— Время: всегда указывай время из рецепта. Если не указано — прикинь по шагам.
— Сложность: «Просто» (≤5 шагов, ≤20 мин), «Средне» (≤10 шагов или ≤45 мин), \
«Сложно» (остальное).
— Раздели ингредиенты на те, что пользователь уже назвал (✅), и те, \
что нужно докупить (🛒).
— Цены в справочнике <prices> указаны за единицу (кг, л, шт и тп). \
Прикинь сколько реально нужно на рецепт и посчитай примерную стоимость. \
Например: чеснок стоит 300 руб./кг, на рецепт нужно 3 зубчика (~30г) = ~10 руб. \
Пиши именно стоимость на рецепт, не цену за кг.
— Если цены нет в справочнике — пропусти, не пиши «цена неизвестна».
— Итого — сумма только тех продуктов, для которых есть цена.
— Выдавай 1–3 лучших рецепта.
— Приготовление: всегда 4–6 шагов, не обрезай на середине.
— Если рецепты частично совпадают — предложи ближайшие, поясни что совпало. \
Не говори «нет рецептов» если в <recipes> что-то есть.
— «Подходящих рецептов нет» только если блок <recipes> пустой.
— На вопросы не про еду: «Я специализируюсь на рецептах. Расскажи, что хочешь приготовить?»
— Не повторяй рецепты из истории диалога.

<recipes>
{recipes}
</recipes>

<prices>
{prices}
</prices>

<history>
{history}
</history>"""


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        _client = AsyncOpenAI(**kwargs)
    return _client


async def translate_to_english(text: str) -> str:
    try:
        client = _get_client()
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "Translate this Russian cooking query to English. Return only the translation, nothing else."},
                {"role": "user", "content": text},
            ],
            max_tokens=200,
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        logger.exception("Translation failed, using original text")
        return text


async def generate_response(
    recipes: str, prices: str, history: str, user_message: str
) -> str:
    """Build prompt from context and call OpenAI API."""
    system = SYSTEM_PROMPT.format(
        recipes=recipes or "Нет подходящих рецептов в базе.",
        prices=prices or "Справочник цен недоступен.",
        history=history or "Нет предыдущих сообщений.",
    )
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature,
        )
        return response.choices[0].message.content or ""
    except Exception:
        logger.exception("OpenAI API call failed")
        return "Сервис генерации временно недоступен. Попробуйте позже."
