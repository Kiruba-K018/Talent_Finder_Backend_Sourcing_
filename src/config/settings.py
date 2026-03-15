from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env that don't match
    )

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    log_level: str = "INFO"

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "talent_finder"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # MongoDB
    mongo_host: str = "mongodb"
    mongo_port: int = 27017
    mongo_user: str = "mongo"
    mongo_password: str = "mongo"
    mongo_db: str = "talent_finder"
    mongo_candidates_collection: str = "candidates"
    
    @property
    def mongo_uri(self) -> str:
        if self.mongo_user and self.mongo_password:
            return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        return f"mongodb://{self.mongo_host}:{self.mongo_port}"

    # ChromaDB
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "candidate_skills"

    # Core Service
    core_service_url: str = "http://app:8000"
    core_service_timeout: int = 30
    core_service_max_retries: int = 3

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    groq_api_key: str = ""

    # Scraping
    chrome_bin: str = "/usr/bin/chromium"
    chromedriver_path: str = "/usr/bin/chromedriver"
    scraper_headless: bool = True
    scraper_min_delay: int = 2
    scraper_max_delay: int = 7
    scraper_page_timeout: int = 60
    linkedin_session_cookie: str = ""
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_headless_login: bool = True  # Attempt login in headless mode
    proxy_url: str = ""

    # Scheduler
    scheduler_poll_interval: int = 60

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "talent_finder_backend_sourcing"
    prometheus_port: int = 9001


@lru_cache
def get_settings() -> Settings:
    return Settings()