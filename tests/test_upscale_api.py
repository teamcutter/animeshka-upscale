from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.app import create_app
from src.core.config import ImageSettings, Settings, StorageSettings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        storage=StorageSettings(dir=tmp_path),
        image=ImageSettings(max_size_mb=1, max_width=256, max_height=256),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def make_png(width: int = 64, height: int = 48) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(("mode", "scale"), [("2k", 2), ("4k", 4)])
def test_upscale_image_flow(client: TestClient, mode: str, scale: int) -> None:
    response = client.post(
        "/api/upscale",
        files={"file": ("frame.png", make_png(), "image/png")},
        data={"mode": mode},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    # TestClient runs background tasks before returning the response.
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert job["mode"] == mode

    result = client.get(job["result_url"])
    assert result.status_code == 200
    assert Image.open(BytesIO(result.content)).size == (64 * scale, 48 * scale)


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


def test_metrics_exposed(client: TestClient) -> None:
    client.get("/health")
    response = client.get("/api/metrics")
    assert response.status_code == 200
