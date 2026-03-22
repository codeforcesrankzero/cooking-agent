# Architecture

## Files

| Path | Description |
|---|---|
| `src/main.py` | Entry point: запускает FastAPI + Telegram-бот |
| `src/api.py` | FastAPI роуты: `POST /query`, `GET /health` |
| `src/config.py` | Настройки через pydantic-settings (`.env`) |
| `src/bot/handlers.py` | Telegram-хендлеры: `/start`, `/reset`, `/help`, текст, кнопки |
| `src/db/init_db.py` | Создание таблиц SQLite при старте |
| `src/db/recipes.py` | FTS5-поиск рецептов по ингредиентам |
| `src/db/prices.py` | Lookup цен из SQLite |
| `src/db/logs.py` | Запись диалогов и фидбэка в таблицу `logs` |
| `src/search/embedding.py` | Singleton-обёртка над `multilingual-e5-small` |
| `src/search/semantic.py` | Семантический поиск через ChromaDB |
| `src/llm/client.py` | OpenAI/OpenRouter клиент, system prompt |
| `src/services/pipeline.py` | Основной пайплайн: разбор → поиск → цены → LLM |
| `src/services/session.py` | Per-chat сессии с TTL и историей |
| `scripts/load_recipes.py` | Загрузка CSV рецептов в SQLite + ChromaDB |
| `scripts/parse_prices.py` | Сид цен (~60 продуктов) в SQLite |
| `tests/test_api.py` | Тесты FastAPI эндпоинтов |
| `tests/test_pipeline.py` | Тесты хелперов пайплайна |
| `tests/test_session.py` | Тесты сессионного менеджера |

## Key entities

### `Session` (`src/services/session.py`)
Хранит историю сообщений одного чата. Поля: `messages: list[dict]`, `last_active: float`. Методы: `add_message`, `is_expired`, `get_history_text`.

### `SessionManager` (`src/services/session.py`)
Dict `chat_id → Session`. Создаёт новую сессию при первом обращении или после TTL. Singleton `session_manager`.

### `process_query` (`src/services/pipeline.py`)
Главная функция пайплайна. Шаги:
1. Извлечь ингредиенты из сообщения (`_extract_ingredients`)
2. Параллельно запустить FTS5 + семантический поиск
3. Объединить и ранжировать результаты (`_combine_results`)
4. Если топ-результат выше `direct_answer_threshold` — отдать карточку без LLM
5. Иначе — подтянуть цены и отправить в LLM
6. Записать в `logs`

### DB tables (SQLite)
| Table | Purpose |
|---|---|
| `recipes` | Рецепты (name, ingredients, steps, minutes, tags) |
| `recipes_fts` | FTS5 виртуальная таблица поверх `recipes` |
| `prices` | Цены продуктов (product_name, price, unit, updated_at) |
| `logs` | Диалоги и фидбэк (chat_id, user_message, bot_response, feedback) |
