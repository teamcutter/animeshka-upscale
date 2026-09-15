from threading import Lock
from uuid import UUID

from src.features.upscale.domain import Job


class InMemoryJobRepository:
    """Draft storage; replaced by PostgreSQL later."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}
        self._lock = Lock()

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: UUID) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
