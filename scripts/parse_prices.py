"""Seed product prices into SQLite.

For MVP: loads a hardcoded price list of ~60 common products.
In production, this would parse prices from perekrestok.ru.

Usage:
    python -m scripts.parse_prices [--db data/cooking.db]
"""

import argparse
import sqlite3

# Approximate prices in RUB as of early 2025 (Moscow, Perekrestok-level)
# Format: (product_name_ru, product_name_en, price_rub, unit)
SEED_PRICES: list[tuple[str, str, float, str]] = [
    # Мясо и птица
    ("курица", "chicken", 280, "кг"),
    ("куриная грудка", "chicken breast", 350, "кг"),
    ("куриные бёдра", "chicken thighs", 260, "кг"),
    ("свинина", "pork", 400, "кг"),
    ("говядина", "beef", 650, "кг"),
    ("фарш", "ground meat", 380, "кг"),
    ("индейка", "turkey", 420, "кг"),
    # Рыба
    ("лосось", "salmon", 1200, "кг"),
    ("треска", "cod", 500, "кг"),
    ("креветки", "shrimp", 800, "кг"),
    # Молочные
    ("молоко", "milk", 80, "л"),
    ("сливки", "cream", 150, "л"),
    ("сметана", "sour cream", 90, "200г"),
    ("творог", "cottage cheese", 120, "200г"),
    ("сыр", "cheese", 600, "кг"),
    ("масло сливочное", "butter", 180, "200г"),
    ("йогурт", "yogurt", 60, "200г"),
    ("яйца", "eggs", 120, "10шт"),
    # Овощи
    ("картофель", "potatoes", 40, "кг"),
    ("лук", "onion", 35, "кг"),
    ("морковь", "carrots", 40, "кг"),
    ("помидоры", "tomatoes", 180, "кг"),
    ("огурцы", "cucumbers", 150, "кг"),
    ("перец болгарский", "bell pepper", 250, "кг"),
    ("чеснок", "garlic", 300, "кг"),
    ("капуста", "cabbage", 35, "кг"),
    ("брокколи", "broccoli", 250, "кг"),
    ("кабачок", "zucchini", 120, "кг"),
    ("баклажан", "eggplant", 180, "кг"),
    ("шпинат", "spinach", 200, "200г"),
    ("грибы", "mushrooms", 250, "кг"),
    # Фрукты
    ("яблоки", "apples", 120, "кг"),
    ("бананы", "bananas", 80, "кг"),
    ("лимон", "lemon", 20, "шт"),
    ("апельсин", "orange", 120, "кг"),
    # Крупы и макароны
    ("рис", "rice", 90, "кг"),
    ("гречка", "buckwheat", 100, "кг"),
    ("макароны", "pasta", 80, "500г"),
    ("спагетти", "spaghetti", 90, "500г"),
    ("овсянка", "oats", 70, "500г"),
    ("мука", "flour", 60, "кг"),
    # Масла и соусы
    ("масло подсолнечное", "vegetable oil", 130, "л"),
    ("масло оливковое", "olive oil", 500, "500мл"),
    ("соевый соус", "soy sauce", 120, "250мл"),
    ("томатная паста", "tomato paste", 60, "200г"),
    ("кетчуп", "ketchup", 90, "350г"),
    ("майонез", "mayonnaise", 100, "400г"),
    ("уксус", "vinegar", 50, "500мл"),
    # Специи и приправы
    ("соль", "salt", 30, "кг"),
    ("перец чёрный", "black pepper", 60, "50г"),
    ("сахар", "sugar", 60, "кг"),
    ("корица", "cinnamon", 50, "50г"),
    ("куркума", "turmeric", 60, "50г"),
    ("паприка", "paprika", 50, "50г"),
    # Консервы и прочее
    ("томаты консервированные", "canned tomatoes", 80, "400г"),
    ("фасоль консервированная", "canned beans", 80, "400г"),
    ("кокосовое молоко", "coconut milk", 150, "400мл"),
    ("хлеб", "bread", 50, "шт"),
    ("мёд", "honey", 300, "500г"),
    ("орехи грецкие", "walnuts", 800, "кг"),
]


def seed_prices(db_path: str) -> int:
    """Insert seed prices into database. Returns count."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            product_name TEXT PRIMARY KEY,
            price REAL,
            unit TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    count = 0
    for name_ru, name_en, price, unit in SEED_PRICES:
        # Insert both Russian and English names
        for name in (name_ru, name_en):
            conn.execute(
                "INSERT OR REPLACE INTO prices (product_name, price, unit) VALUES (?, ?, ?)",
                (name.lower(), price, unit),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed product prices into SQLite")
    parser.add_argument("--db", default="data/cooking.db", help="Path to SQLite database")
    args = parser.parse_args()

    print(f"Seeding prices into {args.db}...")
    n = seed_prices(args.db)
    print(f"Done: {n} price entries inserted.")


if __name__ == "__main__":
    main()
