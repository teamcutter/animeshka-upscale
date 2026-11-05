import pytest

from src.infrastructure.upscale.device import resolve_device


@pytest.mark.parametrize(
    ("requested", "cuda", "mps", "expected"),
    [
        ("auto", False, True, "mps"),
        ("auto", False, False, "cpu"),
        ("auto", True, False, "cuda"),
        ("mps", False, True, "mps"),
        ("mps", False, False, "cpu"),
        ("mps", True, False, "cpu"),
        ("cpu", False, True, "cpu"),
        ("cuda", False, True, "mps"),
        ("cuda", False, False, "cpu"),
    ],
)
def test_device_selection(monkeypatch, requested, cuda, mps, expected):
    monkeypatch.setattr("torch.cuda.is_available", lambda: cuda)
    monkeypatch.setattr("torch.backends.mps.is_available", lambda: mps)
    assert resolve_device(requested) == expected


def test_mps_fallback_is_logged(monkeypatch, caplog):
    monkeypatch.setattr("torch.backends.mps.is_available", lambda: False)
    assert resolve_device("mps") == "cpu"
    assert "MPS not available, falling back to cpu" in caplog.text
