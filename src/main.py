import asyncio

import uvicorn

from src.api.rest.app import create_app
from src.config.settings import get_settings
from src.core.services.scheduler import run_scheduler_loop

settings = get_settings()


async def main():
    app = create_app()

    config = uvicorn.Config(
        app=app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)

    # Run HTTP server and scheduler loop concurrently
    await asyncio.gather(
        server.serve(),
        run_scheduler_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
