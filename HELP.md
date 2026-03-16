# Как запустить проект

## Требования

- Python 3.11+
- Ключи: Telegram Bot Token + OpenAI API Key (или OpenRouter)

## Быстрый старт

```bash
# 1. Клонировать и перейти в папку
git clone https://github.com/codeforcesrankzero/cooking-agent.git
cd cooking-agent

# 2. Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# 3. Установить зависимости
pip install -e ".[dev]"

# 4. Настроить переменные окружения
cp .env.example .env
# Открыть .env и вписать свои ключи:
#   TELEGRAM_BOT_TOKEN=...
#   OPENAI_API_KEY=...
```

## Загрузка данных

Перед первым запуском нужно загрузить рецепты и цены в базу.

```bash
# Скачать CSV с Kaggle (Food.com Recipes and Reviews) и положить в data/recipes.csv

# Загрузить рецепты в SQLite + ChromaDB
python -m scripts.load_recipes --csv data/recipes.csv

# Для быстрой проверки — загрузить только 1000 рецептов:
python -m scripts.load_recipes --csv data/recipes.csv --limit 1000

# Загрузить справочник цен (~60 базовых продуктов)
python -m scripts.parse_prices
```

## Запуск

```bash
# Запуск сервера (FastAPI на порту 8000 + Telegram-бот)
python -m src.main
```

После запуска:
- Telegram-бот работает в polling-режиме
- API доступен на http://localhost:8000
- Healthcheck: `GET /health`
- Запрос рецептов: `POST /query` с телом `{"message": "курица и рис"}`

## Тесты

```bash
python3 -m pytest -v
```

## Структура проекта

```
cooking-agent/
├── src/
│   ├── main.py              # Точка входа: FastAPI + Telegram-бот
│   ├── api.py               # FastAPI эндпоинты (/query, /health)
│   ├── config.py            # Настройки из .env (pydantic-settings)
│   ├── bot/
│   │   └── handlers.py      # Обработчики команд Telegram (/start, /reset, /help, текст)
│   ├── db/
│   │   ├── init_db.py       # Создание таблиц SQLite (recipes, prices, logs)
│   │   ├── recipes.py       # FTS5-поиск рецептов по ингредиентам
│   │   └── prices.py        # Lookup цен из SQLite
│   ├── search/
│   │   ├── semantic.py      # Семантический поиск через ChromaDB
│   │   └── embedding.py     # Embedding-функция (multilingual-e5-small)
│   ├── llm/
│   │   └── client.py        # OpenAI API клиент + system prompt
│   └── services/
│       ├── pipeline.py      # Основной pipeline: парсинг → поиск → цены → LLM
│       └── session.py       # Управление сессиями (история, TTL, сброс)
├── scripts/
│   ├── load_recipes.py      # Загрузка CSV → SQLite + ChromaDB
│   └── parse_prices.py      # Seed-скрипт с ценами (~60 продуктов)
├── tests/
│   ├── test_session.py      # Тесты сессий (TTL, обрезка, сброс)
│   ├── test_pipeline.py     # Тесты pipeline-хелперов (combine, format)
│   └── test_api.py          # Тесты FastAPI эндпоинтов
├── data/                    # Данные (не коммитятся, в .gitignore)
├── design-doc.md            # Дизайн-документ проекта
├── .env.example             # Шаблон переменных окружения
├── pyproject.toml           # Зависимости и настройки проекта
└── .gitignore
```

## Как работает pipeline

```
Сообщение пользователя
    │
    ├─► FTS5: поиск по ингредиентам (SQLite)
    ├─► ChromaDB: семантический поиск по смыслу запроса
    │         │
    │         ▼
    │   Объединение и дедупликация результатов
    │
    ├─► Lookup цен на ингредиенты (SQLite)
    │
    └─► LLM (GPT-4o-mini): генерация ответа на русском
              │
              ▼
        Ответ пользователю
```
