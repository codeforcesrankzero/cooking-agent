"""Load Food.com CSV data into SQLite + ChromaDB.

Usage:
    python -m scripts.load_recipes [--limit N]

By default loads all recipes. Use --limit for faster testing.
"""

import argparse
import csv
import json
import re
import sqlite3
import sys
import time

import chromadb


def parse_r_vector(s: str) -> list[str]:
    """Parse R-style c("a", "b", "c") into a Python list."""
    if not s or s == "NA":
        return []
    s = s.strip()
    if s.startswith('c(') and s.endswith(')'):
        inner = s[2:-1]
        items = []
        current = ""
        in_quotes = False
        escape = False
        for ch in inner:
            if escape:
                current += ch
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_quotes = not in_quotes
            elif ch == "," and not in_quotes:
                items.append(current.strip().strip('"').strip())
                current = ""
            else:
                current += ch
        if current.strip():
            items.append(current.strip().strip('"').strip())
        return [item for item in items if item]
    return [s]


def parse_pt_duration(s: str) -> int | None:
    """Parse ISO 8601 duration like PT2H30M into minutes."""
    if not s or s == "NA":
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", s)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return hours * 60 + mins


def create_tables(conn: sqlite3.Connection) -> None:
    """Create recipes and FTS5 tables."""
    conn.execute("""
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
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts
        USING fts5(name, ingredients, tags, content=recipes, content_rowid=id)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            product_name TEXT PRIMARY KEY,
            price REAL,
            unit TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chat_id INTEGER,
            user_message TEXT,
            bot_response TEXT,
            feedback TEXT
        )
    """)
    conn.commit()


def load_csv_to_sqlite(csv_path: str, db_path: str, limit: int | None = None) -> int:
    """Load recipes from CSV into SQLite. Returns count of loaded recipes."""
    conn = sqlite3.connect(db_path)
    create_tables(conn)

    # Clear existing data for clean reload
    conn.execute("DELETE FROM recipes")
    conn.execute("DELETE FROM recipes_fts")
    conn.commit()

    count = 0
    batch = []
    batch_size = 5000

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if limit and count >= limit:
                break

            name = row.get("Name", "").strip()
            if not name:
                continue

            ingredients = parse_r_vector(row.get("RecipeIngredientParts", ""))
            steps = parse_r_vector(row.get("RecipeInstructions", ""))
            tags = parse_r_vector(row.get("Keywords", ""))
            minutes = parse_pt_duration(row.get("TotalTime", ""))
            description = row.get("Description", "").strip()

            if not ingredients:
                continue

            nutrition_data = {}
            for field in ("Calories", "FatContent", "ProteinContent", "CarbohydrateContent"):
                val = row.get(field, "")
                if val and val != "NA":
                    try:
                        nutrition_data[field] = float(val)
                    except ValueError:
                        pass

            batch.append((
                name,
                json.dumps(ingredients),
                json.dumps(steps),
                minutes,
                json.dumps(tags),
                json.dumps(nutrition_data) if nutrition_data else None,
                description,
            ))
            count += 1

            if len(batch) >= batch_size:
                _insert_batch(conn, batch)
                batch = []
                print(f"  Loaded {count} recipes...", flush=True)

    if batch:
        _insert_batch(conn, batch)

    conn.close()
    return count


def _insert_batch(conn: sqlite3.Connection, batch: list[tuple]) -> None:
    """Insert a batch of recipes and update FTS index."""
    conn.executemany(
        "INSERT INTO recipes (name, ingredients, steps, minutes, tags, nutrition, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        batch,
    )
    # Rebuild FTS index for new rows
    conn.execute("INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild')")
    conn.commit()


def load_to_chromadb(db_path: str, chroma_path: str, limit: int | None = None) -> int:
    """Load recipe embeddings into ChromaDB. Returns count."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = "SELECT id, name, ingredients, tags, description FROM recipes"
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        print("No recipes in SQLite to index.")
        return 0

    from src.search.embedding import MultilingualEmbeddingFunction

    client = chromadb.PersistentClient(path=chroma_path)
    embed_fn = MultilingualEmbeddingFunction()

    # Delete and recreate for clean reload
    try:
        client.delete_collection("recipes")
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name="recipes",
        metadata={"hnsw:space": "cosine"},
        embedding_function=embed_fn,
    )

    batch_size = 500
    count = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        ids = [str(row["id"]) for row in batch]
        documents = []
        for row in batch:
            tags = ""
            try:
                tags = ", ".join(json.loads(row["tags"])) if row["tags"] else ""
            except (json.JSONDecodeError, TypeError):
                pass
            ingredients = ""
            try:
                ing_list = json.loads(row["ingredients"]) if row["ingredients"] else []
                ingredients = ", ".join(ing_list[:15])
            except (json.JSONDecodeError, TypeError):
                pass
            doc = f"{row['name']}. {ingredients}. {tags}. {row['description'] or ''}"
            documents.append(doc)

        collection.add(ids=ids, documents=documents)
        count += len(batch)
        print(f"  Indexed {count}/{len(rows)} recipes in ChromaDB...", flush=True)

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Load recipes into SQLite + ChromaDB")
    parser.add_argument("--csv", default="data/recipes.csv", help="Path to recipes CSV")
    parser.add_argument("--db", default="data/cooking.db", help="Path to SQLite database")
    parser.add_argument("--chroma", default="data/chroma_storage", help="Path to ChromaDB storage")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of recipes to load")
    parser.add_argument("--chroma-only", action="store_true", help="Only rebuild ChromaDB index")
    args = parser.parse_args()

    t0 = time.time()

    if not args.chroma_only:
        print(f"=== Loading recipes from {args.csv} ===")
        print("\n1. Loading CSV → SQLite...")
        n = load_csv_to_sqlite(args.csv, args.db, limit=args.limit)
        print(f"   Done: {n} recipes in {time.time() - t0:.1f}s")

    t1 = time.time()
    print("\n2. Building ChromaDB index (multilingual-e5-small)...")
    m = load_to_chromadb(args.db, args.chroma, limit=args.limit)
    print(f"   Done: {m} recipes indexed in {time.time() - t1:.1f}s")

    print(f"\nTotal time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
