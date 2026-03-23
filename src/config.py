"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения. Загружаются из .env файла."""

    telegram_bot_token: str = ""
    openai_api_key: str = ""
    openai_base_url: str | None = None
    database_path: str = "data/cooking.db"
    chroma_path: str = "data/chroma_storage"

    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 2000
    openai_temperature: float = 0.7

    embedding_model: str = "intfloat/multilingual-e5-small"

    session_ttl_minutes: int = 30
    session_max_messages: int = 10

    search_top_n: int = 10
    direct_answer_threshold: float = 0.9
    relevance_threshold: float = 0.1
    preload_embeddings_on_startup: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
