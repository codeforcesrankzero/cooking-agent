# Отчёт: Инфраструктура (Задание 3)

Андрей — инфра-часть проекта.

## Что сделано

Обвязка для деплоя и мониторинга: Docker-образ приложения, docker-compose с тремя сервисами (app, Prometheus, Grafana), набор Prometheus-метрик с Grafana-дашбордом, debug-логирование через env variable.

## Стек и почему так

**Docker + docker-compose** — стандарт для multi-service проектов. У нас три сервиса (app, prometheus, grafana), compose поднимает всё одной командой. k8s для одного сервиса с нагрузкой в десятки пользователей — оверкилл.

**Python 3.13-slim** — минимальный базовый образ. `build-essential` нужен для нативных расширений (onnxruntime, chromadb). Итоговый образ ~2-3GB из-за PyTorch (тянется через sentence-transformers).

**Prometheus + Grafana** — стандартный open-source стек для мониторинга. prometheus-client для Python — официальная библиотека, минимальный overhead. OpenTelemetry + Jaeger рассматривали, но для учебного проекта избыточно.

## Метрики

| Метрика | Тип | Labels | Что показывает |
|---|---|---|---|
| `cooking_agent_requests_total` | Counter | channel, result | Общее число запросов, ok/error |
| `cooking_agent_request_latency_seconds` | Histogram | channel | End-to-end время ответа |
| `cooking_agent_stage_duration_seconds` | Histogram | stage | Время отдельных стадий: search, prices, llm |
| `cooking_agent_search_hits_total` | Counter | source | Сколько результатов вернул каждый поиск (fts/semantic) |

`channel` = `api` (HTTP) или `bot` (Telegram). `stage` — три стадии pipeline: параллельный поиск, lookup цен, генерация LLM.

## Grafana дашборд

9 панелей:
- Строка 1: RPS, E2E p95 latency, Error rate (stat-панели)
- Строка 2: Requests by result, Search hits по источникам (timeseries)
- Строка 3: Stage duration p50/p95 по стадиям (timeseries)
- Строка 4: Search p95, Prices p95, LLM p95 (stat-панели)

Дашборд провиженится автоматически через Grafana provisioning — JSON лежит в `monitoring/grafana/dashboards/`, datasource в `provisioning/datasources/`.

## Docker healthcheck

FastAPI при старте грузит embedding-модель и ChromaDB. Раньше это блокировало startup event — healthcheck таймаутился. Перенесли preload в фоновый `asyncio.create_task`, `/health` отвечает сразу. В compose стоит `start_period: 60s` на случай первого старта (модель скачивается с HuggingFace).

Флаг `PRELOAD_EMBEDDINGS_ON_STARTUP=false` (по умолчанию в compose) отключает preload — модель загрузится лениво при первом запросе.

## HuggingFace cache

Модель (`intfloat/multilingual-e5-small`, ~120MB) кэшируется в `./data/hf_cache` через `HF_HOME`. Volume `./data:/app/data` сохраняет кэш между перезапусками контейнера.

## Debug-логирование

Добавили `LOG_LEVEL` env variable в compose и `main.py`. По умолчанию `INFO`, для отладки ставим `DEBUG`. На уровне DEBUG pipeline выводит переведённый запрос, количество и top-5 результатов из каждого поиска со скорами. Без этого невозможно понять на каком этапе теряются результаты — очень помогло при отладке качества поиска.

## Сложности

**podman-compose** — `depends_on` с healthcheck не поддерживается в старых версиях. Обходили запуском сервисов вручную по порядку.

**Размер образа** — sentence-transformers тянет PyTorch (~800MB). Для прода можно перейти на ONNX-экспорт + onnxruntime, это сократит образ в 3-4 раза. Пока не делали.

**prometheus-client и multiprocess** — при нескольких uvicorn workers метрики надо собирать через multiprocess mode. Запускаем один worker — проблем нет.

**Рассинхрон ChromaDB и SQLite** — ChromaDB содержит 535к записей, SQLite 522к. При семантическом поиске часть ID из ChromaDB не находится в SQLite (остались от предыдущей загрузки). Из-за этого семантика стабильно возвращает 6 результатов вместо 10. Причина: `load_recipes.py` при загрузке делает `DELETE FROM recipes` с новыми auto-increment ID, а ChromaDB индексируется отдельно.

## Декомпозиция задач

### Сделано

| # | Задача | Кто |
|---|--------|-----|
| 1 | Dockerfile + docker-compose (app, prometheus, grafana) | Андрей |
| 2 | Prometheus метрики (requests, latency, stage duration, search hits) | Андрей |
| 3 | Grafana дашборд с автопровижинингом (9 панелей) | Андрей |
| 4 | Healthcheck + фоновый preload embedding-модели | Андрей |
| 5 | HuggingFace cache через volume | Андрей |
| 6 | Debug-логирование: `LOG_LEVEL`, debug output в pipeline | Андрей + Василий |
| 7 | Конфигурация через pydantic-settings, `.env.example` | Василий |

### Надо сделать

| # | Задача | Кто |
|---|--------|-----|
| 1 | Dev-режим в docker — маунт исходников, чтобы не пересобирать образ на каждое изменение кода | Андрей |
| 2 | Расширить мониторинг — метрика на latency перевода (новый внешний вызов), алерты на error rate | Андрей |
| 3 | Тестовая инфраструктура — pytest в образ, CI pipeline, smoke-тесты через curl по golden set | Андрей + Василий |
| 4 | Почистить startup — заменить deprecated `on_event("startup")` на `lifespan`, сохранять ссылки на background tasks | Андрей |

## Использование LLM

Claude Code для разработки инфраструктуры. Примерное время: ~5 часов, из них ~2 часа с ассистентом. Подписка Claude Pro $20/мес. Claude помогал с: конфигурацией docker-compose, написанием Grafana дашборда (JSON), настройкой prometheus scrape config, отладкой healthcheck.
