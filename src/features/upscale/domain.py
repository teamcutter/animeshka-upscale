from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4


class Mode(StrEnum):
    X2K = "2k"
    X4K = "4k"

    @property
    def scale(self) -> int:
        return 2 if self is Mode.X2K else 4


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Job:
    kind: MediaKind
    mode: Mode
    original_filename: str
    input_path: Path
    id: UUID = field(default_factory=uuid4)
    status: JobStatus = JobStatus.QUEUED
    output_path: Path | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def mark(self, status: JobStatus, *, error: str | None = None) -> None:
        self.status = status
        self.error = error
        self.updated_at = _now()
