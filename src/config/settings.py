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

    # PostgreSQL - from environment variables
    db_url: str = ""
    db_host: str = "34.23.138.181"
    db_port: int = 5432
    db_name: str = "talentfinder"
    db_user: str = "devakirubak"
    db_password: str = "Z7jX6#l5yyNu2sUOBg7"
    postgres_pool_size: int = 2           # Reduced from 10 for Cloud SQL
    postgres_max_overflow: int = 1        # Reduced from 20 for Cloud SQL

    @property
    def postgres_dsn(self) -> str:
        # Use DB_URL if provided (for Cloud Run with Cloud SQL proxy), otherwise construct
        if self.db_url:
            url = self.db_url
            if "postgresql+psycopg://" not in url and "postgresql+asyncpg://" not in url:
                # Ensure psycopg driver
                if "postgresql://" in url:
                    url = url.replace("postgresql://", "postgresql+psycopg://")
                else:
                    url = f"postgresql+psycopg://{url}"
            return url
        # Fallback to constructed URL using psycopg async driver
        from urllib.parse import quote
        encoded_password = quote(self.postgres_password, safe="")
        return f"postgresql+psycopg://{self.postgres_user}:{encoded_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # MongoDB
    mongo_host: str = "mongodb"
    mongo_port: int = 27017
    mongo_user: str = "devakirubak"
    mongo_password: str = "Kiruba@1809"
    mongo_db: str = "talentfinder"
    mongo_authsource: str = "admin"
    mongo_candidates_collection: str = "sourced_candidates"
    atlas_connection_string: str = "mongodb+srv://devakirubak:Kiruba@1809@talentfinder-cluster.0omhk3c.mongodb.net/talentfindeR"  # For MongoDB Atlas
    
    @property
    def mongo_uri(self) -> str:
        if self.atlas_connection_string:
            # Use MongoDB Atlas connection string
            return self.atlas_connection_string
        if self.mongo_user and self.mongo_password:
            return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource={self.mongo_authsource}"
        return f"mongodb://{self.mongo_host}:{self.mongo_port}"

    # ChromaDB
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "candidate_skills"

    # Core Service
    core_service_url: str = "https://talentfinder-backend-core-717740758627.us-east1.run.app"
    core_service_timeout: int = 30
    core_service_max_retries: int = 3

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    groq_api_key: str = ""
    groq_api_key_secondary: str = ""

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

    # Playwright & PostJobFree
    playwright_headless: bool = True
    playwright_timeout: int = 60000  # milliseconds
    serpapi_key: str = ""
    postjobfree_platform_id: str = "22000015-0000-0000-0000-000000000001"
    postjobfree_max_profiles: int = 20  # Max profiles to scrape per run

    # Scheduler
    scheduler_poll_interval: int = 60

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "talent_finder_backend_sourcing"
    prometheus_port: int = 9001


@lru_cache
def get_settings() -> Settings:
    return Settings()