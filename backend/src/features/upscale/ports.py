from pathlib import Path
from typing import Protocol
from uuid import UUID

from PIL import Image

from src.features.upscale.domain import Job, JobStatus


class Upscaler(Protocol):
    """Contract shared with the inference module (RealESRGANUpscaler).

    enhance() upscales the image as is; fitting it into max_size is the service's job.
    """

    scale: int

    def is_available(self) -> bool:
        """True if this upscaler can be loaded on this machine (e.g. its weights exist)."""
        ...

    def load_model(self) -> None: ...

    def warmup(self) -> None: ...

    def enhance(self, image: Image.Image) -> Image.Image: ...

    def unload(self) -> None: ...


class JobRepository(Protocol):
    def add(self, job: Job) -> None: ...

    def get(self, job_id: UUID) -> Job | None: ...

    def update(self, job: Job) -> None: ...

    def list_jobs(
        self, *, status: JobStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Job]: ...

    def claim(self, job_id: UUID) -> Job | None:
        """Atomically move a queued job to processing; None if someone else took it."""
        ...

    def claim_next(self) -> Job | None:
        """Claim the oldest queued job; None if the queue is empty."""
        ...


class FileStorage(Protocol):
    def save_input(self, job_id: UUID, filename: str, data: bytes) -> Path: ...

    def output_path(self, job_id: UUID, suffix: str) -> Path: ...
