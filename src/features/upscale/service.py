import logging
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from uuid import UUID

from PIL import Image, UnidentifiedImageError

from src.core.config import ImageSettings, VideoSettings
from src.features.upscale.domain import Job, JobStatus, MediaKind, Mode
from src.features.upscale.ports import FileStorage, JobRepository, Upscaler
from src.shared.errors import (
    InvalidMediaError,
    JobNotReadyError,
    NotFoundError,
    UnsupportedMediaTypeError,
)

logger = logging.getLogger(__name__)

IMAGE_FORMATS = {"PNG", "JPEG", "WEBP", "BMP"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
MB = 1024 * 1024


class UpscaleService:
    def __init__(
        self,
        jobs: JobRepository,
        storage: FileStorage,
        upscalers: Mapping[Mode, Upscaler],
        image_settings: ImageSettings,
        video_settings: VideoSettings,
    ) -> None:
        self._jobs = jobs
        self._storage = storage
        self._upscalers = upscalers
        self._image = image_settings
        self._video = video_settings

    @property
    def image_limit_bytes(self) -> int:
        return self._image.max_size_mb * MB

    @property
    def video_limit_bytes(self) -> int:
        return self._video.max_size_mb * MB

    def create_image_job(self, filename: str, data: bytes, mode: Mode) -> Job:
        try:
            with Image.open(BytesIO(data)) as img:
                fmt, (width, height) = img.format, img.size
        except UnidentifiedImageError as exc:
            raise UnsupportedMediaTypeError("File is not a supported image") from exc

        if fmt not in IMAGE_FORMATS:
            raise UnsupportedMediaTypeError(f"Unsupported image format: {fmt}")
        if width > self._image.max_width or height > self._image.max_height:
            raise InvalidMediaError(
                f"Image {width}x{height} exceeds {self._image.max_width}x{self._image.max_height}"
            )
        return self._create_job(MediaKind.IMAGE, filename, data, mode)

    def create_video_job(self, filename: str, data: bytes, mode: Mode) -> Job:
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise UnsupportedMediaTypeError(f"Unsupported video extension: {suffix or 'none'}")
        return self._create_job(MediaKind.VIDEO, filename, data, mode)

    def get_job(self, job_id: UUID) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        return job

    def get_result_path(self, job_id: UUID) -> Path:
        job = self.get_job(job_id)
        if job.status is not JobStatus.DONE or job.output_path is None:
            raise JobNotReadyError(f"Job {job_id} is {job.status}")
        return job.output_path

    def process_image(self, job_id: UUID, max_size: int) -> None:
        job = self.get_job(job_id)
        self._set_status(job, JobStatus.PROCESSING)
        try:
            upscaler = self._upscalers[job.mode]
            with Image.open(job.input_path) as img:
                result = upscaler.enhance(img.convert("RGB"), max_size=max_size)
            output = self._storage.output_path(job.id, ".png")
            result.save(output, format="PNG")
        except Exception as exc:
            logger.exception("Image job %s failed", job.id)
            self._set_status(job, JobStatus.FAILED, error=str(exc))
            return
        job.output_path = output
        self._set_status(job, JobStatus.DONE)

    def process_video(self, job_id: UUID) -> None:
        job = self.get_job(job_id)
        # TODO: frame-wise enhance() + ffmpeg re-mux once the inference module is ready.
        self._set_status(job, JobStatus.FAILED, error="Video upscaling is not implemented yet")

    def _create_job(self, kind: MediaKind, filename: str, data: bytes, mode: Mode) -> Job:
        job = Job(kind=kind, mode=mode, original_filename=filename, input_path=Path())
        job.input_path = self._storage.save_input(job.id, filename, data)
        self._jobs.add(job)
        logger.info("Created %s job %s (mode=%s)", kind, job.id, mode)
        return job

    def _set_status(self, job: Job, status: JobStatus, *, error: str | None = None) -> None:
        job.mark(status, error=error)
        self._jobs.update(job)
