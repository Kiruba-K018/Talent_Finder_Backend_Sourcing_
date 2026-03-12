from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.api.rest.routes import health, sse
from src.observability.logging.logger import configure_logging
from src.observability.tracing.tracer import configure_tracing
from src.observability.metrics.prometheus import start_metrics_server
from src.data.clients.mongo_client import close_mongo_client
from src.data.clients.postgres_client import dispose_engine
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    configure_tracing()
    start_metrics_server()
    yield
    await close_mongo_client()
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="talent_finder_backend_sourcing",
        version="0.1.0",
        lifespan=lifespan,
    )
    FastAPIInstrumentor.instrument_app(app)
    app.include_router(health.router)
    app.include_router(sse.router)
    return app