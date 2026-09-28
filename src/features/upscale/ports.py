from pathlib import Path
from typing import Protocol
from uuid import UUID

from PIL import Image

from src.features.upscale.domain import Job


class Upscaler(Protocol):
    """Contract shared with the inference module (RealESRGANUpscaler)."""

    scale: int

    def load_model(self) -> None: ...

    def warmup(self, max_size: int = 1920) -> None: ...

    def enhance(self, image: Image.Image, max_size: int = 1920) -> Image.Image: ...

    def unload(self) -> None: ...


class JobRepository(Protocol):
    def add(self, job: Job) -> None: ...

    def get(self, job_id: UUID) -> Job | None: ...

    def update(self, job: Job) -> None: ...


class FileStorage(Protocol):
    def save_input(self, job_id: UUID, filename: str, data: bytes) -> Path: ...

    def output_path(self, job_id: UUID, suffix: str) -> Path: ...
