from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest

from src.features.upscale.domain import (
    FileRole,
    Job,
    JobStatus,
    MediaFile,
    MediaKind,
    Mode,
    now_utc,
)
from src.infrastructure.db.engine import create_db_engine, create_session_factory
from src.infrastructure.db.migrate import upgrade_database
from src.infrastructure.storage.sql import SqlJobRepository
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture
def repo(database_url: str) -> Iterator[SqlJobRepository]:
    engine = create_db_engine(database_url)
    upgrade_database(engine)
    yield SqlJobRepository(create_session_factory(engine))
    engine.dispose()


def make_job(**kwargs) -> Job:
    return Job(
        kind=MediaKind.IMAGE,
        mode=Mode.X2K,
        original_filename="frame.png",
        input=MediaFile(
            role=FileRole.INPUT, path=Path("in/frame.png"), size_bytes=10, width=4, height=3
        ),
        **kwargs,
    )


def test_add_and_get_roundtrip(repo: SqlJobRepository) -> None:
    job = make_job(max_size=1024)
    repo.add(job)

    loaded = repo.get(job.id)
    assert loaded == job
    assert loaded is not None and loaded.created_at.tzinfo is not None


def test_get_unknown_returns_none(repo: SqlJobRepository) -> None:
    assert repo.get(make_job().id) is None


def test_update_saves_output_and_metrics(repo: SqlJobRepository) -> None:
    job = make_job()
    repo.add(job)

    job.output = MediaFile(role=FileRole.OUTPUT, path=Path("out/x.png"), size_bytes=40)
    job.metrics = {"processing_seconds": 1.5, "psnr": 30.0}
    job.mark(JobStatus.DONE)
    repo.update(job)
    assert repo.get(job.id) == job

    job.metrics = {"processing_seconds": 2.0}
    repo.update(job)
    loaded = repo.get(job.id)
    assert loaded is not None and loaded.metrics == {"processing_seconds": 2.0}


def test_claim_is_atomic(repo: SqlJobRepository) -> None:
    job = make_job()
    repo.add(job)

    claimed = repo.claim(job.id)
    assert claimed is not None and claimed.status is JobStatus.PROCESSING
    assert repo.claim(job.id) is None


def test_claim_next_takes_oldest_first(repo: SqlJobRepository) -> None:
    start = now_utc()
    newer = make_job(created_at=start)
    older = make_job(created_at=start - timedelta(minutes=1))
    done = make_job(created_at=start - timedelta(minutes=2), status=JobStatus.DONE)
    for job in (newer, older, done):
        repo.add(job)

    first, second = repo.claim_next(), repo.claim_next()
    assert first is not None and first.id == older.id
    assert second is not None and second.id == newer.id
    assert repo.claim_next() is None


def test_list_jobs_filters_and_paginates(repo: SqlJobRepository) -> None:
    start = now_utc()
    jobs = [make_job(created_at=start + timedelta(seconds=i)) for i in range(3)]
    jobs[0].status = JobStatus.FAILED
    for job in jobs:
        repo.add(job)

    assert [j.id for j in repo.list_jobs()] == [jobs[2].id, jobs[1].id, jobs[0].id]
    assert [j.id for j in repo.list_jobs(status=JobStatus.FAILED)] == [jobs[0].id]
    assert [j.id for j in repo.list_jobs(limit=1, offset=1)] == [jobs[1].id]


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="row locking needs PostgreSQL")
def test_parallel_workers_never_take_the_same_job(repo: SqlJobRepository) -> None:
    for _ in range(20):
        repo.add(make_job())

    def drain() -> list:
        taken = []
        while (job := repo.claim_next()) is not None:
            taken.append(job.id)
        return taken

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [f.result() for f in [pool.submit(drain) for _ in range(4)]]

    claimed = [job_id for taken in results for job_id in taken]
    assert len(claimed) == 20
    assert len(set(claimed)) == 20
