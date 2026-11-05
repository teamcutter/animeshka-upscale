from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.features.upscale.domain import Mode
from src.infrastructure.upscale.remote import RemoteMPSUpscaler
from src.infrastructure.upscale.stub import StubUpscaler
from src.mps_bridge import create_bridge
from tests.conftest import make_png


class RecordingStub(StubUpscaler):
    loads = 0
    calls = 0

    def load_model(self):
        self.loads += 1

    def enhance(self, image):
        self.calls += 1
        return super().enhance(image)


def test_container_routes_frames_through_authenticated_bridge(make_settings, monkeypatch):
    settings = make_settings()
    monkeypatch.setattr("torch.backends.mps.is_available", lambda: True)
    gpu = RecordingStub(2)
    fallback = RecordingStub(2)
    app = create_bridge(settings, upscalers={Mode.X2K: gpu})
    token_path = settings.storage.dir / "mps-bridge.token"
    with TestClient(app) as client:
        assert client.post("/enhance/2k", content=make_png()).status_code == 401

        def open_from_container(request, timeout):
            if isinstance(request, str):
                response = client.get("/health")
            else:
                response = client.post(
                    "/enhance/2k", content=request.data, headers=dict(request.header_items())
                )
            assert response.status_code == 200, response.text
            return BytesIO(response.content)

        monkeypatch.setattr("src.infrastructure.upscale.remote.urlopen", open_from_container)
        remote = RemoteMPSUpscaler(fallback, "http://host.docker.internal:8766", token_path)
        remote.load_model()
        remote.warmup()
        result = remote.enhance(Image.open(BytesIO(make_png())))
        assert result.size == (128, 96)
        assert remote.device == "mps"
        assert gpu.calls == 1
        assert fallback.calls == 0
        assert fallback.loads == 0
        assert token_path.stat().st_mode & 0o777 == 0o600
        remote.unload()


def test_bridge_unavailable_uses_cpu_fallback(tmp_path):
    fallback = RecordingStub(2)
    remote = RemoteMPSUpscaler(fallback, "http://unused", tmp_path / "missing-token")
    remote.load_model()
    result = remote.enhance(Image.new("RGB", (16, 12)))
    assert result.size == (32, 24)
    assert remote.device == "cpu"
    assert fallback.loads == 1
    assert fallback.calls == 1


def test_bridge_disconnect_during_job_falls_back_once(tmp_path, monkeypatch):
    token_path = tmp_path / "token"
    token_path.write_text("secret")
    fallback = RecordingStub(2)
    remote = RemoteMPSUpscaler(fallback, "http://bridge", token_path)
    monkeypatch.setattr(remote, "_available", lambda: True)
    remote.load_model()

    def disconnected(*args, **kwargs):
        raise ConnectionError("Bridge stopped")

    monkeypatch.setattr("src.infrastructure.upscale.remote.urlopen", disconnected)
    frame = Image.new("RGB", (16, 12))
    assert remote.enhance(frame).size == (32, 24)
    assert remote.enhance(frame).size == (32, 24)
    assert remote.device == "cpu"
    assert fallback.loads == 1
    assert fallback.calls == 2


def test_bridge_never_claims_mps_when_unavailable(make_settings, monkeypatch):
    monkeypatch.setattr("torch.backends.mps.is_available", lambda: False)
    app = create_bridge(make_settings(), upscalers={Mode.X2K: StubUpscaler(2)})
    with pytest.raises(RuntimeError, match="MPS available"), TestClient(app):
        pass
