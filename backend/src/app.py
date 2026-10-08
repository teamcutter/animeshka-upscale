import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
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
        # With an external worker the API never runs the model, so it doesn't load it.
        container.startup(load_models=settings.worker.embedded)
        yield
        container.shutdown()

    app = FastAPI(title=settings.app.title, version="0.2.0", lifespan=lifespan)
    app.state.container = container

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/health", tags=["health"])
    async def health() -> JSONResponse:
        database_ok = await run_in_threadpool(container.database_ok)
        return JSONResponse(
            status_code=200 if database_ok else 503,
            content={
                "status": "ok" if database_ok else "degraded",
                "database": "ok" if database_ok else "unavailable",
                "backend": settings.upscale.backend,
                "worker": "embedded" if settings.worker.embedded else "external",
                "modes": {
                    mode.value: ok for mode, ok in container.upscale_service.available_modes.items()
                },
            },
        )

    app.include_router(upscale_router)
    Instrumentator().instrument(app).expose(app, endpoint="/api/metrics", include_in_schema=False)
    return app
