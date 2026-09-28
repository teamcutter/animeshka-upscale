from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.features.upscale.domain import Job, JobStatus, MediaKind, Mode


class JobResponse(BaseModel):
    id: UUID
    kind: MediaKind
    mode: Mode
    status: JobStatus
    filename: str
    result_url: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: Job) -> "JobResponse":
        return cls(
            id=job.id,
            kind=job.kind,
            mode=job.mode,
            status=job.status,
            filename=job.original_filename,
            result_url=f"/api/jobs/{job.id}/result" if job.status is JobStatus.DONE else None,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
