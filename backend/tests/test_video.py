import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.features.upscale.domain import Mode
from src.worker import run
from tests.conftest import SettingsFactory, register


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(("mode", "scale"), [("2k", 2), ("4k", 4)])
@pytest.mark.parametrize("audio", [False, True])
def test_video_flow(client: TestClient, video_factory, tmp_path: Path, mode, scale, audio) -> None:
    data = video_factory(audio=audio)
    response = client.post(
        "/api/upscale/video",
        files={"file": ("clip.mp4", data, "video/mp4")},
        data={"mode": mode},
    )
    assert response.status_code == 202, response.text
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert job["kind"] == "video"
    assert (job["input"]["width"], job["input"]["height"]) == (64, 48)
    assert (job["output"]["width"], job["output"]["height"]) == (64 * scale, 48 * scale)
    assert job["metrics"]["frame_count"] == 6
    assert job["metrics"]["fps"] == 12
    assert job["metrics"]["duration_seconds"] == 0.5
    assert job["metrics"]["processing_seconds"] >= 0
    assert job["metrics"]["megapixels_per_second"] > 0
    assert job["metrics"]["quality_sample_count"] == 1
    assert 0 < job["metrics"]["psnr_db"] <= 100
    assert 0 < job["metrics"]["ssim"] <= 1
    assert job["metrics"]["sharpness_bicubic"] > 0
    assert job["metrics"]["sharpness_output"] > 0
    result = client.get(job["result_url"])
    assert result.status_code == 200
    assert result.headers["content-type"] == "video/mp4"
    path = tmp_path / "result.mp4"
    path.write_bytes(result.content)
    streams = probe(path)["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert int(video["nb_frames"]) == 6
    assert float(video["duration"]) == pytest.approx(0.5)
    audio_streams = [stream for stream in streams if stream["codec_type"] == "audio"]
    assert len(audio_streams) == int(audio)
    if audio:
        assert audio_streams[0]["codec_name"] == "aac"
        assert float(audio_streams[0]["duration"]) == pytest.approx(0.5, abs=0.05)
    partial = client.get(job["result_url"], headers={"Range": "bytes=0-31"})
    assert partial.status_code == 206
    assert partial.content == result.content[:32]


def test_video_output_limit_and_fractional_fps(client: TestClient, video_factory, tmp_path: Path):
    response = client.post(
        "/api/upscale/video",
        files={"file": ("clip.mp4", video_factory(fps="30000/1001"), "video/mp4")},
        data={"mode": "4k", "max_size": "100"},
    )
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert (job["output"]["width"], job["output"]["height"]) == (100, 76)
    result = tmp_path / "result.mp4"
    result.write_bytes(client.get(job["result_url"]).content)
    stream = probe(result)["streams"][0]
    numerator, denominator = map(int, stream["avg_frame_rate"].split("/"))
    assert numerator / denominator == pytest.approx(30000 / 1001)


def test_video_rejects_large_upload(client: TestClient):
    response = client.post(
        "/api/upscale/video",
        files={"file": ("large.mp4", b"x" * (1024 * 1024 + 1), "video/mp4")},
    )
    assert response.status_code == 413


def test_video_external_worker(make_settings: SettingsFactory, video_factory):
    settings = make_settings(embedded=False)
    with TestClient(create_app(settings)) as client:
        register(client)
        response = client.post(
            "/api/upscale/video",
            files={"file": ("clip.mp4", video_factory(), "video/mp4")},
            data={"start_seconds": "0.1666666667", "end_seconds": "0.4166666667"},
        )
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"
        assert client.get(f"/api/jobs/{job_id}/original").status_code == 409
        assert run(settings, once=True) == 1
        job = client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "done", job["error"]
        assert job["start_seconds"] == pytest.approx(1 / 6)
        assert job["end_seconds"] == pytest.approx(5 / 12)
        assert job["metrics"]["frame_count"] == 3
        assert client.get(job["result_url"]).status_code == 200


def test_video_failure_cleans_partial_output(client: TestClient, video_factory, monkeypatch):
    upscaler = client.app.state.container.upscalers[Mode.X2K]
    enhance = upscaler.enhance
    frames = 0

    def fail_second_frame(image):
        nonlocal frames
        frames += 1
        if frames == 2:
            raise RuntimeError("Inference failed")
        return enhance(image)

    monkeypatch.setattr(upscaler, "enhance", fail_second_frame)
    response = client.post(
        "/api/upscale/video", files={"file": ("clip.mp4", video_factory(), "video/mp4")}
    )
    job_id = response.json()["id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert job["error"] == "Inference failed"
    assert job["result_url"] is None
    root = client.app.state.container.settings.storage.dir
    assert not list((root / "outputs").iterdir())
    assert client.get(f"/api/jobs/{job_id}/result").status_code == 409


def test_video_missing_ffmpeg_is_actionable(client: TestClient, video_factory, monkeypatch):
    data = video_factory()
    monkeypatch.setattr("src.features.upscale.video.shutil.which", lambda _: None)
    response = client.post("/api/upscale/video", files={"file": ("clip.mp4", data, "video/mp4")})
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "failed"
    assert "requires FFmpeg" in job["error"]


def test_video_quality_averages_sampled_frames(client: TestClient, video_factory, monkeypatch):
    calls = []

    def measure(source, result):
        assert result.width == source.width * 2
        calls.append(source.size)
        return {"psnr_db": 10.0 * len(calls), "ssim": 0.2 * len(calls)}

    monkeypatch.setattr("src.features.upscale.service.quality_metrics", measure)
    response = client.post(
        "/api/upscale/video",
        files={"file": ("clip.mp4", video_factory(duration=2.6), "video/mp4")},
    )
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert job["metrics"]["frame_count"] == 32
    assert len(calls) == 2
    assert job["metrics"]["quality_sample_count"] == 2
    assert job["metrics"]["psnr_db"] == 15
    assert job["metrics"]["ssim"] == 0.3


def test_video_quality_failure_does_not_fail_upscale(
    client: TestClient, video_factory, monkeypatch
):
    calls = 0

    def measure(source, result):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Analytics unavailable")
        return {"psnr_db": 25.0, "ssim": 0.9}

    monkeypatch.setattr("src.features.upscale.service.quality_metrics", measure)
    response = client.post(
        "/api/upscale/video",
        files={"file": ("clip.mp4", video_factory(duration=2.6), "video/mp4")},
    )
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert job["metrics"]["quality_sample_count"] == 1
    assert job["metrics"]["psnr_db"] == 25
    assert job["metrics"]["ssim"] == 0.9
    assert client.get(job["result_url"]).status_code == 200


@pytest.mark.parametrize("audio", [False, True])
def test_selected_video_interval(client: TestClient, video_factory, tmp_path: Path, audio):
    data = video_factory(duration=2, audio=audio)
    response = client.post(
        "/api/upscale/video",
        files={"file": ("clip.mp4", data, "video/mp4")},
        data={"start_seconds": "0.5", "end_seconds": "1"},
    )
    assert response.status_code == 202, response.text
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    assert job["start_seconds"] == 0.5
    assert job["end_seconds"] == 1
    assert job["metrics"]["frame_count"] == 6
    assert job["metrics"]["duration_seconds"] == 0.5
    output = tmp_path / "selected.mp4"
    output.write_bytes(client.get(job["result_url"]).content)
    streams = probe(output)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    assert int(video["nb_frames"]) == 6
    assert float(video["duration"]) == pytest.approx(0.5)
    if audio:
        sound = next(s for s in streams if s["codec_type"] == "audio")
        assert float(sound["duration"]) == pytest.approx(0.5, abs=0.05)
    source = cv2.VideoCapture(str(tmp_path / "clip.mp4"))
    result = cv2.VideoCapture(str(output))
    try:
        source.set(cv2.CAP_PROP_POS_FRAMES, 6)
        ok, original = source.read()
        assert ok
        ok, enhanced = result.read()
        assert ok
        expected = cv2.resize(original, (128, 96), interpolation=cv2.INTER_LANCZOS4)
        assert np.abs(enhanced.astype(float) - expected.astype(float)).mean() < 10
    finally:
        source.release()
        result.release()


@pytest.mark.parametrize(
    "values",
    [
        {"start_seconds": "-1"},
        {"start_seconds": "2"},
        {"start_seconds": "1", "end_seconds": "1"},
        {"start_seconds": "1", "end_seconds": "0.5"},
        {"end_seconds": "3"},
        {"start_seconds": "nan"},
        {"end_seconds": "inf"},
        {"start_seconds": "0.01", "end_seconds": "0.02"},
    ],
)
def test_invalid_video_range_not_queued(client: TestClient, video_factory, tmp_path: Path, values):
    response = client.post(
        "/api/upscale/video",
        files={"file": ("clip.mp4", video_factory(duration=2), "video/mp4")},
        data=values,
    )
    assert response.status_code == 422, response.text
    assert client.get("/api/jobs").json() == []
    assert not list((tmp_path / "data" / "inputs").iterdir())


@pytest.mark.parametrize("audio", [False, True])
def test_preview_without_upscaling(client: TestClient, video_factory, tmp_path: Path, audio):
    response = client.post(
        "/api/upscale/video/preview",
        files={"file": ("clip.mp4", video_factory(duration=2, audio=audio), "video/mp4")},
        data={"start_seconds": "0.5", "duration_seconds": "0.5"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "video/mp4"
    assert float(response.headers["x-video-duration"]) == 2
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/jobs").json() == []
    output = tmp_path / "preview.mp4"
    output.write_bytes(response.content)
    streams = probe(output)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert video["width"] <= 640
    assert float(video["duration"]) == pytest.approx(0.5)
    assert len([s for s in streams if s["codec_type"] == "audio"]) == int(audio)


def test_preview_rejects_out_of_bounds_range(client: TestClient, video_factory):
    response = client.post(
        "/api/upscale/video/preview",
        files={"file": ("clip.mp4", video_factory(), "video/mp4")},
        data={"start_seconds": "5"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("extension", ["mp4", "avi"])
def test_comparison_original_is_aligned_cached_and_private(
    client: TestClient, video_factory, tmp_path: Path, monkeypatch, extension
):
    data = video_factory(duration=2, fps="30000/1001", audio=True)
    source_path = tmp_path / "clip.mp4"
    if extension == "avi":
        source_path = tmp_path / "clip.avi"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "clip.mp4"),
                "-c:v", "mpeg4", "-q:v", "2", "-c:a", "pcm_s16le", str(source_path),
            ],
            check=True, capture_output=True, timeout=30,
        )
        data = source_path.read_bytes()
    response = client.post(
        "/api/upscale/video",
        files={"file": (source_path.name, data, "application/octet-stream")},
        data={"start_seconds": "0.51", "end_seconds": "1.01"},
    )
    job = client.get(f"/api/jobs/{response.json()['id']}").json()
    assert job["status"] == "done", job["error"]
    original = client.get(job["original_url"])
    assert original.status_code == 200
    assert original.headers["content-type"] == "video/mp4"
    preview_path = tmp_path / "comparison.mp4"
    preview_path.write_bytes(original.content)
    streams = probe(preview_path)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert (video["width"], video["height"]) == (64, 48)
    assert int(video["nb_frames"]) == job["metrics"]["frame_count"] == 15
    assert float(video["duration"]) == pytest.approx(job["metrics"]["duration_seconds"], abs=0.001)
    assert any(s["codec_type"] == "audio" for s in streams)
    source, comparison = cv2.VideoCapture(str(source_path)), cv2.VideoCapture(str(preview_path))
    try:
        source.set(cv2.CAP_PROP_POS_FRAMES, 16)
        ok, expected = source.read()
        assert ok
        ok, actual = comparison.read()
        assert ok
        assert np.abs(actual.astype(float) - expected.astype(float)).mean() < 10
    finally:
        source.release()
        comparison.release()

    def unexpected_conversion(*args, **kwargs):
        raise AssertionError("Comparison source must be cached")

    monkeypatch.setattr("src.features.upscale.service.upscale_video", unexpected_conversion)
    partial = client.get(job["original_url"], headers={"Range": "bytes=0-31"})
    assert partial.status_code == 206
    assert partial.content == original.content[:32]
    assert client.post(f"/api/jobs/{job['id']}/publish").status_code == 200
    published = client.get("/api/feed").json()["items"][0]
    owner_cookies = dict(client.cookies)
    client.cookies.clear()
    register(client, email="viewer@example.com")
    assert client.get(job["original_url"]).status_code == 404
    assert client.get(published["original_url"]).content == original.content
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    root = client.app.state.container.settings.storage.dir
    cache = root / "outputs" / f"{job['id']}.original.mp4"
    assert not cache.exists()
    assert client.get(job["original_url"]).status_code == 404
    assert client.get(published["original_url"]).status_code == 404
