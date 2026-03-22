"""Telegram bot handlers."""

import logging

from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.logs import write_feedback
from src.services.pipeline import process_query
from src.services.session import session_manager

logger = logging.getLogger(__name__)

FEEDBACK_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="👍", callback_data="feedback:like"),
    InlineKeyboardButton(text="👎", callback_data="feedback:dislike"),
    InlineKeyboardButton(text="Ещё варианты", callback_data="more_options"),
]])


def register_handlers(dp: Dispatcher) -> None:
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_reset, Command("reset"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(handle_text)
    dp.callback_query.register(handle_feedback, F.data.startswith("feedback:"))
    dp.callback_query.register(handle_more_options, F.data == "more_options")


async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "Привет! Я кулинарный помощник на базе LLM.\n\n"
        "Расскажи, какие продукты у тебя есть, и я подберу рецепты. "
        "Или опиши ситуацию — например, «ужин на свидание» или "
        "«быстрый обед после тренировки».\n\n"
        "Команды:\n"
        "/reset — сбросить контекст диалога\n"
        "/help — справка\n\n"
        "⚠️ Я бот на базе LLM — ответы могут быть неточными, "
        "а цены ориентировочные."
    )


async def cmd_reset(message: types.Message) -> None:
    session_manager.reset(message.chat.id)
    await message.answer("Контекст сброшен.")


async def cmd_help(message: types.Message) -> None:
    await message.answer(
        "Что я умею:\n"
        "• Подбираю рецепты по списку продуктов\n"
        "• Ищу рецепты по сценарию (свидание, спорт, быстрый обед)\n"
        "• Считаю примерную стоимость докупки\n"
        "• Веду диалог — можно уточнять и просить альтернативы\n\n"
        "Просто напиши, что у тебя есть или что хочешь приготовить!"
    )


async def _send_response(target: types.Message, text: str) -> None:
    """Send response with Markdown, fallback to plain text."""
    try:
        await target.answer(text, parse_mode="Markdown", reply_markup=FEEDBACK_KB)
    except Exception:
        await target.answer(text, reply_markup=FEEDBACK_KB)


async def handle_text(message: types.Message) -> None:
    if not message.text:
        return
    response = await process_query(message.text, message.chat.id)
    await _send_response(message, response)


async def handle_feedback(callback: types.CallbackQuery) -> None:
    feedback_type = callback.data.split(":")[1] if callback.data else "unknown"
    logger.info("Feedback from chat %s: %s", callback.message.chat.id, feedback_type)
    await write_feedback(callback.message.chat.id, feedback_type)
    await callback.answer("Спасибо за отзыв!")


async def handle_more_options(callback: types.CallbackQuery) -> None:
    response = await process_query("Покажи ещё варианты", callback.message.chat.id)
    await _send_response(callback.message, response)
    await callback.answer()
