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
    input: FileInfo
    output: FileInfo | None
    metrics: dict[str, float]
    result_url: str | None
    error: str | None
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
            input=FileInfo.from_media(job.input),
            output=FileInfo.from_media(job.output) if job.output else None,
            metrics=job.metrics,
            result_url=f"/api/jobs/{job.id}/result" if done else None,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
