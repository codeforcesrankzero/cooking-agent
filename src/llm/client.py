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
⏱ Время · 📊 Сложность

🥘 Ингредиенты (переведи на русский):
 • продукт 1
 • продукт 2
 ➕ _Нужно докупить:_ продукт — цена

📝 Приготовление (переведи, кратко, не более 6 шагов):
 1. Шаг
 2. Шаг

Правила:
— Переводи названия рецептов и ингредиенты на русский.
— Сложность определяй по количеству шагов и времени: \
«Просто» (≤5 шагов, ≤20 мин), «Средне» (≤10 шагов или ≤45 мин), \
«Сложно» (остальное).
— Цены бери ТОЛЬКО из справочника. Если цена неизвестна — пиши «цена неизвестна», \
не выдумывай.
— Выдавай 1–3 лучших рецепта, не больше.
— Если подходящих рецептов нет — скажи честно и предложи уточнить запрос.
— На вопросы не про еду — вежливо верни к теме: «Я специализируюсь на рецептах. \
Расскажи, что хочешь приготовить?»
— Не повторяй рецепты, которые уже были в истории диалога.

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
