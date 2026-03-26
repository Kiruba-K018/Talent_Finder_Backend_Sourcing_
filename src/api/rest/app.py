from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.error_handler import setup_error_handlers
from src.api.middleware.logging import LoggingMiddleware
from src.api.rest.routes import health, sourcing
from src.data.clients.mongo_client import close_mongo_client
from src.data.clients.postgres_client import dispose_engine
from src.observability.logging.logger import configure_logging
from src.observability.metrics.prometheus import start_metrics_server
from src.observability.tracing.tracer import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info("Configuring logging...")
        configure_logging()
    except Exception as e:
        logger.warning(f"Failed to configure logging: {e}")

    try:
        logger.info("Configuring tracing...")
        configure_tracing()
    except Exception as e:
        logger.warning(f"Failed to configure tracing: {e}")

    try:
        logger.info("Starting metrics server...")
        start_metrics_server()
    except Exception as e:
        logger.warning(f"Failed to start metrics server: {e}")

    yield

    try:
        logger.info("Closing mongo client...")
        await close_mongo_client()
    except Exception as e:
        logger.warning(f"Failed to close mongo client: {e}")

    try:
        logger.info("Disposing database engine...")
        await dispose_engine()
    except Exception as e:
        logger.warning(f"Failed to dispose engine: {e}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="talent_finder_backend_sourcing",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(LoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    setup_error_handlers(app)

    app.include_router(health.router)
    app.include_router(sourcing.router)
    return app
