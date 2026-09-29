from fastapi.testclient import TestClient

from src.app import create_app
from src.worker import run
from tests.conftest import SettingsFactory, make_png


def test_external_worker_processes_queued_jobs(make_settings: SettingsFactory) -> None:
    settings = make_settings(embedded=False)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["worker"] == "external"

        job_ids = []
        for mode in ("2k", "4k"):
            response = client.post(
                "/api/upscale",
                files={"file": ("frame.png", make_png(), "image/png")},
                data={"mode": mode},
            )
            job_ids.append(response.json()["id"])

        # Without the worker the API only queues jobs.
        for job_id in job_ids:
            assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"

        assert run(settings, once=True) == 2

        for job_id in job_ids:
            job = client.get(f"/api/jobs/{job_id}").json()
            assert job["status"] == "done"
            assert client.get(job["result_url"]).status_code == 200


def test_worker_with_empty_queue_exits(make_settings: SettingsFactory) -> None:
    assert run(make_settings(embedded=False), once=True) == 0
