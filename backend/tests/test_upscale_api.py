from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.app import create_app
from src.core.config import UpscaleSettings
from tests.conftest import SettingsFactory, make_png


def upload(client: TestClient, png: bytes | None = None, **data: str) -> dict:
    response = client.post(
        "/api/upscale",
        files={"file": ("frame.png", png or make_png(), "image/png")},
        data=data,
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "backend": "stub",
        "worker": "embedded",
        "modes": {"2k": True, "4k": True},
    }


@pytest.mark.parametrize(("mode", "scale"), [("2k", 2), ("4k", 4)])
def test_upscale_image_flow(client: TestClient, mode: str, scale: int) -> None:
    job_id = upload(client, mode=mode)["id"]

    # TestClient runs background tasks before returning the response.
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert job["mode"] == mode
    assert job["input"] == {"size_bytes": len(make_png()), "width": 64, "height": 48}
    assert job["output"]["width"] == 64 * scale
    assert job["output"]["height"] == 48 * scale
    assert job["metrics"]["processing_seconds"] >= 0

    result = client.get(job["result_url"])
    assert result.status_code == 200
    assert Image.open(BytesIO(result.content)).size == (64 * scale, 48 * scale)


def test_max_size_limits_output(client: TestClient) -> None:
    job_id = upload(client, make_png(200, 100), mode="2k", max_size="128")["id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["max_size"] == 128
    assert (job["output"]["width"], job["output"]["height"]) == (128, 64)


def test_upscale_rejects_non_image(client: TestClient) -> None:
    response = client.post("/api/upscale", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_upscale_rejects_large_resolution(client: TestClient) -> None:
    response = client.post(
        "/api/upscale", files={"file": ("big.png", make_png(512, 512), "image/png")}
    )
    assert response.status_code == 422


def test_upscale_rejects_large_file(client: TestClient) -> None:
    response = client.post(
        "/api/upscale", files={"file": ("big.png", b"0" * (1024 * 1024 + 1), "image/png")}
    )
    assert response.status_code == 413


def test_upscale_rejects_unknown_mode(client: TestClient) -> None:
    response = client.post(
        "/api/upscale",
        files={"file": ("frame.png", make_png(), "image/png")},
        data={"mode": "8k"},
    )
    assert response.status_code == 422


def test_video_job_is_created(client: TestClient) -> None:
    response = client.post("/api/upscale/video", files={"file": ("clip.mp4", b"fake", "video/mp4")})
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["kind"] == "video"
    assert job["status"] == "failed"
    assert job["input"]["size_bytes"] == 4


def test_video_rejects_unknown_extension(client: TestClient) -> None:
    response = client.post("/api/upscale/video", files={"file": ("clip.exe", b"fake", "video/mp4")})
    assert response.status_code == 415


def test_unknown_job_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_result_not_ready(client: TestClient) -> None:
    response = client.post("/api/upscale/video", files={"file": ("clip.mp4", b"fake", "video/mp4")})
    result = client.get(f"/api/jobs/{response.json()['id']}/result")
    assert result.status_code == 409


def test_list_jobs_newest_first_with_status_filter(client: TestClient) -> None:
    image_id = upload(client)["id"]
    video = client.post("/api/upscale/video", files={"file": ("clip.mp4", b"x", "video/mp4")})
    video_id = video.json()["id"]

    jobs = client.get("/api/jobs").json()
    assert [job["id"] for job in jobs] == [video_id, image_id]

    done = client.get("/api/jobs", params={"status": "done"}).json()
    assert [job["id"] for job in done] == [image_id]

    page = client.get("/api/jobs", params={"limit": 1, "offset": 1}).json()
    assert [job["id"] for job in page] == [image_id]


def test_realesrgan_without_weights_disables_modes(
    make_settings: SettingsFactory, tmp_path: Path
) -> None:
    # Real backend but no .pth files: the API still starts and reports both modes as unavailable.
    settings = make_settings()
    settings.upscale = UpscaleSettings(backend="realesrgan", model_path=tmp_path / "no-weights")
    with TestClient(create_app(settings)) as client:
        health = client.get("/health").json()
        assert health["backend"] == "realesrgan"
        assert health["modes"] == {"2k": False, "4k": False}

        response = client.post(
            "/api/upscale",
            files={"file": ("frame.png", make_png(), "image/png")},
            data={"mode": "2k"},
        )
        assert response.status_code == 422
        assert "not available" in response.json()["detail"]
        assert client.get("/api/jobs").json() == []


def test_jobs_survive_restart(make_settings: SettingsFactory) -> None:
    settings = make_settings()
    with TestClient(create_app(settings)) as first:
        job_id = upload(first)["id"]

    with TestClient(create_app(settings)) as second:
        job = second.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "done"
        assert second.get(job["result_url"]).status_code == 200


def test_metrics_exposed(client: TestClient) -> None:
    client.get("/health")
    response = client.get("/api/metrics")
    assert response.status_code == 200
