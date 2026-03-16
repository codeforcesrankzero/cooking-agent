"""Entry point: starts FastAPI server with Telegram bot as a background task."""

import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher

from src.api import app
from src.bot.handlers import register_handlers
from src.config import settings
from src.db.init_db import init_database
from src.search.embedding import preload_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def start_bot() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    register_handlers(dp)
    logger.info("Starting Telegram bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


@app.on_event("startup")
async def on_startup() -> None:
    db_dir = os.path.dirname(settings.database_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    await init_database(settings.database_path)
    logger.info("Database initialized at %s", settings.database_path)

    logger.info("Preloading embedding model...")
    await asyncio.to_thread(preload_model)
    logger.info("Embedding model ready")

    from src.search.semantic import _get_collection
    await asyncio.to_thread(_get_collection)
    logger.info("ChromaDB collection ready")

    if settings.telegram_bot_token:
        asyncio.create_task(start_bot())


def main() -> None:
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
