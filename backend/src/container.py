import logging
from dataclasses import dataclass

from sqlalchemy import Engine, text

from src.core.config import Settings, UpscaleSettings
from src.features.upscale.domain import Mode
from src.features.upscale.ports import Upscaler
from src.features.upscale.service import UpscaleService
from src.infrastructure.db.engine import create_db_engine, create_session_factory
from src.infrastructure.db.migrate import upgrade_database
from src.infrastructure.storage.files import LocalFileStorage
from src.infrastructure.storage.sql import SqlJobRepository
from src.infrastructure.upscale import RealESRGANUpscaler, UpscalerConfig
from src.infrastructure.upscale.stub import StubUpscaler

logger = logging.getLogger(__name__)


def build_upscalers(settings: UpscaleSettings) -> dict[Mode, Upscaler]:
    if settings.backend == "stub":
        return {mode: StubUpscaler(mode.scale) for mode in Mode}

    return {
        mode: RealESRGANUpscaler(
            UpscalerConfig(
                device=settings.device,
                tile_size=settings.tile_size,
                model_path=str(settings.resolved_model_path),
                scale=mode.scale,
            )
        )
        for mode in Mode
    }


@dataclass
class Container:
    settings: Settings
    engine: Engine
    upscalers: dict[Mode, Upscaler]
    upscale_service: UpscaleService
    models_loaded: bool = False

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        engine = create_db_engine(settings.database.url)
        upscalers = build_upscalers(settings.upscale)
        service = UpscaleService(
            jobs=SqlJobRepository(create_session_factory(engine)),
            storage=LocalFileStorage(settings.storage.dir),
            upscalers=upscalers,
            image_settings=settings.image,
            video_settings=settings.video,
        )
        return cls(settings=settings, engine=engine, upscalers=upscalers, upscale_service=service)

    def startup(self, *, load_models: bool = True) -> None:
        if self.settings.database.auto_migrate:
            upgrade_database(self.engine)
        if load_models:
            for upscaler in self.upscalers.values():
                upscaler.load_model()
                upscaler.warmup()
            self.models_loaded = True
            logger.info("Upscalers ready (backend=%s)", self.settings.upscale.backend)

    def shutdown(self) -> None:
        if self.models_loaded:
            for upscaler in self.upscalers.values():
                upscaler.unload()
            self.models_loaded = False
        self.engine.dispose()

    def database_ok(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            logger.exception("Database health check failed")
            return False
        return True
