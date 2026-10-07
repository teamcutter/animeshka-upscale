from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from src.features.upscale.domain import (
    FileRole,
    Job,
    JobStatus,
    MediaFile,
    MediaKind,
    Mode,
    now_utc,
)
from src.infrastructure.db.models import FileRow, JobRow, MetricRow


def _aware(value: datetime) -> datetime:
    # SQLite drops the timezone; everything is stored in UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _to_file(row: FileRow) -> MediaFile:
    return MediaFile(
        role=FileRole(row.role),
        path=Path(row.path),
        size_bytes=row.size_bytes,
        width=row.width,
        height=row.height,
    )


def _to_domain(row: JobRow) -> Job:
    files = {FileRole(f.role): _to_file(f) for f in row.files}
    return Job(
        id=row.id,
        kind=MediaKind(row.kind),
        mode=Mode(row.mode),
        status=JobStatus(row.status),
        original_filename=row.original_filename,
        max_size=row.max_size,
        input=files[FileRole.INPUT],
        output=files.get(FileRole.OUTPUT),
        error=row.error,
        metrics={m.name: m.value for m in row.metrics},
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _apply(row: JobRow, job: Job) -> None:
    row.kind = job.kind.value
    row.mode = job.mode.value
    row.status = job.status.value
    row.original_filename = job.original_filename
    row.max_size = job.max_size
    row.error = job.error
    row.created_at = job.created_at
    row.updated_at = job.updated_at

    files = {f.role: f for f in row.files}
    for media in (job.input, job.output):
        if media is None:
            continue
        file_row = files.pop(media.role.value, None)
        if file_row is None:
            file_row = FileRow(role=media.role.value)
            row.files.append(file_row)
        file_row.path = str(media.path)
        file_row.size_bytes = media.size_bytes
        file_row.width = media.width
        file_row.height = media.height
    for stale in files.values():
        row.files.remove(stale)

    metrics = {m.name: m for m in row.metrics}
    for name, value in job.metrics.items():
        metric_row = metrics.pop(name, None)
        if metric_row is None:
            row.metrics.append(MetricRow(name=name, value=value, created_at=now_utc()))
        else:
            metric_row.value = value
    for stale in metrics.values():
        row.metrics.remove(stale)


class SqlJobRepository:
    """Jobs, their files and metrics in PostgreSQL (or SQLite for local runs/tests)."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def add(self, job: Job) -> None:
        with self._sessions.begin() as session:
            row = JobRow(id=job.id)
            _apply(row, job)
            session.add(row)

    def get(self, job_id: UUID) -> Job | None:
        with self._sessions() as session:
            row = session.get(JobRow, job_id)
            return _to_domain(row) if row else None

    def update(self, job: Job) -> None:
        with self._sessions.begin() as session:
            row = session.get(JobRow, job.id)
            if row is None:
                raise LookupError(f"Job {job.id} does not exist")
            _apply(row, job)

    def list_jobs(
        self, *, status: JobStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Job]:
        stmt = select(JobRow).order_by(JobRow.created_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(JobRow.status == status.value)
        with self._sessions() as session:
            return [_to_domain(row) for row in session.scalars(stmt)]

    def claim(self, job_id: UUID) -> Job | None:
        with self._sessions.begin() as session:
            return self._take(session, job_id)

    def claim_next(self) -> Job | None:
        stmt = (
            select(JobRow.id)
            .where(JobRow.status == JobStatus.QUEUED.value)
            .order_by(JobRow.created_at)
            .limit(1)
            # PostgreSQL: parallel workers skip rows another worker is claiming.
            .with_for_update(skip_locked=True)
        )
        with self._sessions.begin() as session:
            job_id = session.scalar(stmt)
            return None if job_id is None else self._take(session, job_id)

    @staticmethod
    def _take(session: Session, job_id: UUID) -> Job | None:
        # The status check in WHERE makes the claim atomic even without row locks (SQLite).
        result = session.execute(
            update(JobRow)
            .where(JobRow.id == job_id, JobRow.status == JobStatus.QUEUED.value)
            .values(status=JobStatus.PROCESSING.value, updated_at=now_utc())
        )
        if result.rowcount != 1:
            return None
        row = session.get(JobRow, job_id, populate_existing=True)
        return _to_domain(row) if row else None
