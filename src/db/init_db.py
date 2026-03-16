"""Database initialization: create SQLite tables for recipes, prices, and logs."""

import aiosqlite


async def init_database(db_path: str) -> None:
    """Create all required tables if they don't exist."""
    async with aiosqlite.connect(db_path) as db:
        # Main recipes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                steps TEXT NOT NULL,
                minutes INTEGER,
                tags TEXT,
                nutrition TEXT,
                description TEXT
            )
        """)

        # FTS5 virtual table for ingredient search
        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts
            USING fts5(name, ingredients, tags, content=recipes, content_rowid=id)
        """)

        # Prices table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                product_name TEXT PRIMARY KEY,
                price REAL,
                unit TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Logs table for tracking conversations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                chat_id INTEGER,
                user_message TEXT,
                bot_response TEXT,
                feedback TEXT
            )
        """)

        await db.commit()
