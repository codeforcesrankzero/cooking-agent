"""Price lookup from SQLite."""

import aiosqlite

from src.config import settings


async def get_prices(products: list[str]) -> dict[str, float | None]:
    if not products:
        return {}
    normalized = {p.lower(): p for p in products}
    placeholders = ",".join("?" for _ in normalized)
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            f"SELECT product_name, price FROM prices WHERE product_name IN ({placeholders})",
            list(normalized.keys()),
        )
        rows = await cursor.fetchall()
    found = {row[0]: row[1] for row in rows}
    return {orig: found.get(low) for low, orig in normalized.items()}
