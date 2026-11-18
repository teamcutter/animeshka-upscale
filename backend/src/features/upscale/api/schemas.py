from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.features.upscale.domain import Job, JobStatus, MediaFile, MediaKind, Mode


class FileInfo(BaseModel):
    size_bytes: int
    width: int | None
    height: int | None

    @classmethod
    def from_media(cls, media: MediaFile) -> "FileInfo":
        # The server-side path is deliberately not exposed.
        return cls(size_bytes=media.size_bytes, width=media.width, height=media.height)


class JobResponse(BaseModel):
    id: UUID
    kind: MediaKind
    mode: Mode
    status: JobStatus
    filename: str
    max_size: int
    start_seconds: float
    end_seconds: float | None
    input: FileInfo
    output: FileInfo | None
    metrics: dict[str, float]
    result_url: str | None
    original_url: str
    error: str | None
    published: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: Job) -> "JobResponse":
        done = job.status is JobStatus.DONE
        return cls(
            id=job.id,
            kind=job.kind,
            mode=job.mode,
            status=job.status,
            filename=job.original_filename,
            max_size=job.max_size,
            start_seconds=job.start_seconds,
            end_seconds=job.end_seconds,
            input=FileInfo.from_media(job.input),
            output=FileInfo.from_media(job.output) if job.output else None,
            metrics=job.metrics,
            result_url=f"/api/jobs/{job.id}/result" if done else None,
            original_url=f"/api/jobs/{job.id}/original",
            error=job.error,
            published=job.published_at is not None,
            published_at=job.published_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
