import aiosqlite

from src.config import settings


async def write_log(chat_id: int, user_message: str, bot_response: str) -> None:
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "INSERT INTO logs (chat_id, user_message, bot_response) VALUES (?, ?, ?)",
                (chat_id, user_message, bot_response),
            )
            await db.commit()
    except Exception:
        pass


async def write_feedback(chat_id: int, feedback: str) -> None:
    try:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "INSERT INTO logs (chat_id, feedback) VALUES (?, ?)",
                (chat_id, feedback),
            )
            await db.commit()
    except Exception:
        pass
