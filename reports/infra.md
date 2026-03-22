# Отчёт: Инфраструктура (Задание 3)

## Что сделано

Добавлена инфраструктура для деплоя и мониторинга: Docker-образ приложения, docker-compose с тремя сервисами (app, Prometheus, Grafana), и набор метрик с Grafana-дашбордом.

## Стек и обоснование

**Docker + docker-compose** — стандарт для учебных проектов с несколькими сервисами. Альтернатива (k8s) избыточна для одного сервиса с нагрузкой в десятки пользователей.

**Python 3.13-slim** — минимальный образ, достаточный для наших зависимостей. `build-essential` нужен для компиляции нативных расширений (onnxruntime, chromadb). Итоговый размер образа ~2-3GB с моделями.

**Prometheus + Grafana** — де-факто стандарт для open-source мониторинга. prometheus-client для Python — официальная библиотека с минимальным overhead. Альтернатива (OpenTelemetry + Jaeger) избыточна для учебного проекта.

## Метрики

| Метрика | Тип | Labels | Что измеряет |
|---|---|---|---|
| `cooking_agent_requests_total` | Counter | channel, result | Всего запросов |
| `cooking_agent_request_latency_seconds` | Histogram | channel | End-to-end latency |
| `cooking_agent_answer_path_total` | Counter | path | Direct vs LLM |
| `cooking_agent_stage_duration_seconds` | Histogram | stage | Время стадий: search, prices, llm |

**channel** = `api` (HTTP) или `bot` (Telegram). **stage** — три стадии пайплайна: параллельный поиск (FTS5+ChromaDB), lookup цен, генерация LLM.

## Grafana dashboard

9 панелей в трёх строках:
- Строка 1: RPS (stat), E2E p95 (stat), Error rate (stat)
- Строка 2: Requests by result (timeseries), Direct vs LLM (timeseries)
- Строка 3: Stage duration p50/p95 по всем стадиям (timeseries)
- Строка 4: Search p95, Prices p95, LLM p95 (stat)

## Docker healthcheck

FastAPI при старте запускает preload embedding-модели и ChromaDB. Раньше это блокировало startup-event, из-за чего healthcheck таймаутился. Решено через `asyncio.create_task` — preload идёт фоново, `/health` отвечает сразу. В docker-compose выставлен большой `start_period: 60s` для первого старта (загрузка модели с HuggingFace).

Флаг `PRELOAD_EMBEDDINGS_ON_STARTUP=false` в docker-compose отключает preload — модель загружается лениво при первом запросе. Это ускоряет старт контейнера.

## HuggingFace cache

Модель (`intfloat/multilingual-e5-small`, ~120MB) кэшируется в `./data/hf_cache` через `HF_HOME`. При перезапуске контейнера модель не скачивается повторно (volume `./data:/app/data`).

## Сложности

**podman-compose** — `depends_on` с healthcheck не поддерживается в старых версиях podman-compose. Обходное решение: запускать сервисы вручную по порядку или использовать `docker compose` с podman socket.

**Размер образа** — sentence-transformers тянет PyTorch (~800MB). Для продакшена стоит рассмотреть ONNX-экспорт модели и onnxruntime вместо PyTorch, что сократит образ в 3-4 раза.

**prometheus-client и multiprocess** — при запуске uvicorn с несколькими workers метрики нужно собирать через multiprocess mode. Для учебного проекта запускаем один worker, проблем нет.
