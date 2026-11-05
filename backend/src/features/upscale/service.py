import logging
import time
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

from src.core.config import ImageSettings, VideoSettings
from src.features.upscale.domain import FileRole, Job, JobStatus, MediaFile, MediaKind, Mode
from src.features.upscale.ports import FileStorage, JobRepository, Upscaler
from src.features.upscale.quality import quality_metrics
from src.features.upscale.video import (
    create_video_preview,
    probe_video,
    upscale_video,
    video_frame_range,
)
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
VIDEO_QUALITY_FRAME_INTERVAL = 30


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

    def create_video_job(
        self,
        filename: str,
        data: bytes,
        mode: Mode,
        max_size: int = 1920,
        *,
        owner_id: UUID,
        start_seconds: float = 0,
        end_seconds: float | None = None,
    ) -> Job:
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise UnsupportedMediaTypeError(f"Unsupported video extension: {suffix or 'none'}")
        return self._create_job(
            MediaKind.VIDEO,
            filename,
            data,
            mode,
            max_size=max_size,
            owner_id=owner_id,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )

    def preview_video(
        self, filename: str, data: bytes, start_seconds: float, duration_seconds: float
    ) -> tuple[bytes, float]:
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise UnsupportedMediaTypeError(f"Unsupported video extension: {suffix or 'none'}")
        with TemporaryDirectory() as directory:
            source = Path(directory) / f"source{suffix}"
            output = Path(directory) / "preview.mp4"
            source.write_bytes(data)
            info = probe_video(source)
            video_frame_range(info, start_seconds, None)
            duration = min(duration_seconds, info.duration_seconds - start_seconds)
            create_video_preview(source, output, start_seconds, duration)
            return output.read_bytes(), info.duration_seconds

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
            try:
                if job.kind is MediaKind.VIDEO:
                    self._upscale_video(job)
                else:
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
            output_megapixels * job.metrics.get("frame_count", 1) / duration_seconds
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
        # psnr_db / ssim / sharpness_* (lost in the merge of #13 and #14, see quality.py).
        try:
            job.metrics.update(quality_metrics(source, result))
        except Exception:
            # Analytics must never fail an otherwise good upscale.
            logger.exception("Quality metrics failed for job %s", job.id)

    def _upscale_video(self, job: Job) -> None:
        upscaler = self._upscalers[job.mode]
        processing_seconds = 0.0
        frame_index = 0
        quality_samples = 0
        quality_totals: dict[str, float] = {}

        def enhance(frame: Image.Image) -> Image.Image:
            nonlocal processing_seconds, frame_index, quality_samples
            started = time.perf_counter()
            source = fit_to_output(frame, job.max_size, upscaler.scale)
            result = upscaler.enhance(source)
            processing_seconds += time.perf_counter() - started
            # Match image-job quality metrics, averaging the first and every 30th frame.
            # Sampling keeps analytics affordable without retaining decoded frames in memory.
            if frame_index % VIDEO_QUALITY_FRAME_INTERVAL == 0:
                try:
                    sample = quality_metrics(source, result)
                except Exception:
                    logger.exception("Quality metrics failed for video job %s", job.id)
                else:
                    for name, value in sample.items():
                        quality_totals[name] = quality_totals.get(name, 0.0) + value
                    quality_samples += 1
            frame_index += 1
            return result

        output = self._storage.output_path(job.id, ".mp4")
        info = upscale_video(
            job.input.path,
            output,
            enhance,
            start_seconds=job.start_seconds,
            end_seconds=job.end_seconds,
        )
        job.output = MediaFile(
            role=FileRole.OUTPUT,
            path=output,
            size_bytes=output.stat().st_size,
            width=info.width,
            height=info.height,
        )
        output_mp = info.width * info.height / 1e6
        job.metrics.update(
            processing_seconds=round(processing_seconds, 4),
            frame_count=float(info.frames),
            fps=info.fps,
            duration_seconds=info.frames / info.fps,
            input_size_bytes=float(job.input.size_bytes),
            output_size_bytes=float(job.output.size_bytes),
            input_megapixels=round(megapixels(job.input) or 0, 4),
            output_megapixels=round(output_mp, 4),
            quality_sample_count=float(quality_samples),
        )
        if quality_samples:
            job.metrics.update(
                {name: round(total / quality_samples, 6) for name, total in quality_totals.items()}
            )
        if processing_seconds > 0:
            job.metrics["megapixels_per_second"] = round(
                output_mp * info.frames / processing_seconds, 4
            )

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
        start_seconds: float = 0,
        end_seconds: float | None = None,
    ) -> Job:
        self._require_mode(mode)
        job_id = uuid4()
        path = self._storage.save_input(job_id, filename, data)
        if kind is MediaKind.VIDEO:
            try:
                info = probe_video(path)
                video_frame_range(info, start_seconds, end_seconds)
            except Exception:
                self._storage.delete(path)
                raise
            width, height = info.width, info.height
        job = Job(
            id=job_id,
            owner_id=owner_id,
            kind=kind,
            mode=mode,
            original_filename=filename,
            max_size=max_size,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
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
