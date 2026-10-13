import logging
import time
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

from src.core.config import ImageSettings, VideoSettings
from src.features.upscale.domain import FileRole, Job, JobStatus, MediaFile, MediaKind, Mode
from src.features.upscale.ports import FileStorage, JobRepository, Upscaler
from src.shared import metrics
from src.shared.errors import (
    InvalidMediaError,
    JobNotReadyError,
    ModeUnavailableError,
    NotFoundError,
    UnsupportedMediaTypeError,
)

logger = logging.getLogger(__name__)

IMAGE_FORMATS = {"PNG", "JPEG", "WEBP", "BMP"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
MB = 1024 * 1024


def fit_to_output(image: Image.Image, max_size: int, scale: int) -> Image.Image:
    """Downsize the input so the upscaled output fits into max_size on its long side."""
    limit = max(max_size // scale, 1)
    if max(image.size) <= limit:
        return image
    image = image.copy()
    image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
    return image


def megapixels(media: MediaFile | None) -> float | None:
    """Size of a media file in megapixels, when its resolution is known."""
    if media is None or not media.width or not media.height:
        return None
    return media.width * media.height / 1e6


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
    def available_modes(self) -> dict[Mode, bool]:
        """Which modes this server can run (weights present); exposed in /health."""
        return {mode: upscaler.is_available() for mode, upscaler in self._upscalers.items()}

    def _require_mode(self, mode: Mode) -> None:
        upscaler = self._upscalers.get(mode)
        if upscaler is None or not upscaler.is_available():
            raise ModeUnavailableError(
                f"Mode {mode} is not available on this server (missing weights)"
            )

    @property
    def video_limit_bytes(self) -> int:
        return self._video.max_size_mb * MB

    def create_image_job(
        self, filename: str, data: bytes, mode: Mode, max_size: int = 1920, *, owner_id: UUID
    ) -> Job:
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
        return self._create_job(
            MediaKind.IMAGE,
            filename,
            data,
            mode,
            max_size,
            owner_id=owner_id,
            width=width,
            height=height,
        )

    def create_video_job(self, filename: str, data: bytes, mode: Mode, *, owner_id: UUID) -> Job:
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise UnsupportedMediaTypeError(f"Unsupported video extension: {suffix or 'none'}")
        return self._create_job(
            MediaKind.VIDEO, filename, data, mode, max_size=1920, owner_id=owner_id
        )

    def get_job(self, job_id: UUID, owner_id: UUID) -> Job:
        job = self._jobs.get(job_id)
        # Someone else's job is reported as missing: its id must not leak that it exists.
        if job is None or job.owner_id != owner_id:
            raise NotFoundError(f"Job {job_id} not found")
        return job

    def list_jobs(
        self,
        owner_id: UUID,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        return self._jobs.list_jobs(owner_id=owner_id, status=status, limit=limit, offset=offset)

    def get_result_path(self, job_id: UUID, owner_id: UUID) -> Path:
        job = self.get_job(job_id, owner_id)
        if job.status is not JobStatus.DONE or job.output is None:
            raise JobNotReadyError(f"Job {job_id} is {job.status}")
        return job.output.path

    def delete_job(self, job_id: UUID, owner_id: UUID) -> None:
        job = self.get_job(job_id, owner_id)
        if not self._jobs.delete(job_id):
            raise JobNotReadyError(f"Job {job_id} is being processed, try again later")
        for media in (job.input, job.output):
            if media is not None:
                self._storage.delete(media.path)
        logger.info("Deleted job %s", job_id)

    def process_job(self, job_id: UUID) -> None:
        """Process one specific job (embedded mode: called right after upload)."""
        job = self._jobs.claim(job_id)
        if job is None:
            logger.info("Job %s is already taken or finished", job_id)
            return
        self._run(job)

    def process_next(self) -> bool:
        """Process the oldest queued job (worker mode). Returns False if the queue is empty."""
        job = self._jobs.claim_next()
        if job is None:
            return False
        self._run(job)
        return True

    def _run(self, job: Job) -> None:
        logger.info("Processing %s job %s (mode=%s)", job.kind, job.id, job.mode)
        started = time.perf_counter()
        metrics.JOBS_IN_PROGRESS.labels(kind=job.kind.value).inc()
        try:
            if job.kind is MediaKind.VIDEO:
                # TODO: frame-wise enhance() + ffmpeg re-mux (src/cli.py has the pipeline).
                self._finish(job, JobStatus.FAILED, error="Video upscaling is not implemented yet")
            else:
                try:
                    self._upscale_image(job)
                except Exception as exc:
                    logger.exception("Job %s failed", job.id)
                    self._finish(job, JobStatus.FAILED, error=str(exc))
                else:
                    self._finish(job, JobStatus.DONE)
        finally:
            metrics.JOBS_IN_PROGRESS.labels(kind=job.kind.value).dec()
            self._observe(job, time.perf_counter() - started)

    def _observe(self, job: Job, duration_seconds: float) -> None:
        """Publish a finished job to Prometheus (plotted in Grafana)."""
        output = job.output
        input_megapixels = megapixels(job.input)
        output_megapixels = megapixels(output)
        throughput = (
            output_megapixels / duration_seconds
            if output_megapixels is not None and duration_seconds > 0
            else None
        )
        metrics.observe_job(
            kind=job.kind.value,
            mode=job.mode.value,
            status=job.status.value,
            duration_seconds=duration_seconds,
            input_bytes=job.input.size_bytes,
            output_bytes=output.size_bytes if output is not None else None,
            input_megapixels=input_megapixels,
            output_megapixels=output_megapixels,
            megapixels_per_second=throughput,
        )

    def _upscale_image(self, job: Job) -> None:
        upscaler = self._upscalers[job.mode]
        started = time.perf_counter()
        with Image.open(job.input.path) as img:
            source = fit_to_output(img.convert("RGB"), job.max_size, upscaler.scale)
        result = upscaler.enhance(source)
        elapsed = time.perf_counter() - started

        output = self._storage.output_path(job.id, ".png")
        result.save(output, format="PNG")
        input_megapixels = megapixels(job.input)
        output_megapixels = result.width * result.height / 1e6
        job.output = MediaFile(
            role=FileRole.OUTPUT,
            path=output,
            size_bytes=output.stat().st_size,
            width=result.width,
            height=result.height,
        )
        job.metrics["processing_seconds"] = round(elapsed, 4)
        job.metrics["output_megapixels"] = round(output_megapixels, 4)
        job.metrics["input_size_bytes"] = float(job.input.size_bytes)
        job.metrics["output_size_bytes"] = float(job.output.size_bytes)
        if input_megapixels is not None:
            job.metrics["input_megapixels"] = round(input_megapixels, 4)
        if elapsed > 0:
            job.metrics["megapixels_per_second"] = round(output_megapixels / elapsed, 4)

    def _create_job(
        self,
        kind: MediaKind,
        filename: str,
        data: bytes,
        mode: Mode,
        max_size: int,
        *,
        owner_id: UUID,
        width: int | None = None,
        height: int | None = None,
    ) -> Job:
        self._require_mode(mode)
        job_id = uuid4()
        path = self._storage.save_input(job_id, filename, data)
        job = Job(
            id=job_id,
            owner_id=owner_id,
            kind=kind,
            mode=mode,
            original_filename=filename,
            max_size=max_size,
            input=MediaFile(
                role=FileRole.INPUT, path=path, size_bytes=len(data), width=width, height=height
            ),
        )
        self._jobs.add(job)
        logger.info("Queued %s job %s (mode=%s)", kind, job.id, mode)
        return job

    def _finish(self, job: Job, status: JobStatus, *, error: str | None = None) -> None:
        job.mark(status, error=error)
        self._jobs.update(job)
