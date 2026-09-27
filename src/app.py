import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.container import Container
from src.core.config import Settings
from src.features.upscale.api.router import router as upscale_router
from src.shared.errors import AppError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(
        level=settings.log.level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    container = Container.build(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container.startup()
        yield
        container.shutdown()

    app = FastAPI(title=settings.app.title, version="0.1.0", lifespan=lifespan)
    app.state.container = container

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "device": settings.upscale.device}

    app.include_router(upscale_router)
    Instrumentator().instrument(app).expose(app, endpoint="/api/metrics", include_in_schema=False)
    return app
