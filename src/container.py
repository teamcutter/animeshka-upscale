from dataclasses import dataclass

from src.core.config import Settings
from src.features.upscale.domain import Mode
from src.features.upscale.ports import Upscaler
from src.features.upscale.service import UpscaleService
from src.infrastructure.storage.files import LocalFileStorage
from src.infrastructure.storage.memory import InMemoryJobRepository
from src.infrastructure.upscale.stub import StubUpscaler


@dataclass
class Container:
    settings: Settings
    upscalers: dict[Mode, Upscaler]
    upscale_service: UpscaleService

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        upscalers: dict[Mode, Upscaler] = {mode: StubUpscaler(mode.scale) for mode in Mode}
        service = UpscaleService(
            jobs=InMemoryJobRepository(),
            storage=LocalFileStorage(settings.storage.dir),
            upscalers=upscalers,
            image_settings=settings.image,
            video_settings=settings.video,
        )
        return cls(settings=settings, upscalers=upscalers, upscale_service=service)

    def startup(self) -> None:
        for upscaler in self.upscalers.values():
            upscaler.load_model()
            upscaler.warmup()

    def shutdown(self) -> None:
        for upscaler in self.upscalers.values():
            upscaler.unload()
