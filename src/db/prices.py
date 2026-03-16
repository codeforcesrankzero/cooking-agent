"""Price lookup from SQLite."""

import aiosqlite

from src.config import settings


async def get_prices(products: list[str]) -> dict[str, float | None]:
    """Look up prices for a list of products."""
    result: dict[str, float | None] = {}
    async with aiosqlite.connect(settings.database_path) as db:
        for product in products:
            cursor = await db.execute(
                "SELECT price FROM prices WHERE product_name = ?",
                (product.lower(),),
            )
            row = await cursor.fetchone()
            result[product] = row[0] if row else None
    return result
