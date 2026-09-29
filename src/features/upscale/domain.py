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


class FileRole(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class MediaFile:
    role: FileRole
    path: Path
    size_bytes: int
    width: int | None = None
    height: int | None = None


@dataclass
class Job:
    kind: MediaKind
    mode: Mode
    original_filename: str
    input: MediaFile
    max_size: int = 1920
    id: UUID = field(default_factory=uuid4)
    status: JobStatus = JobStatus.QUEUED
    output: MediaFile | None = None
    error: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)

    def mark(self, status: JobStatus, *, error: str | None = None) -> None:
        self.status = status
        self.error = error
        self.updated_at = now_utc()
