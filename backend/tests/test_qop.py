import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.features.qop.models import Predictor, Term
from src.features.qop.service import bundle_path
from tests.conftest import SettingsFactory, make_png


def install_trained(client: TestClient) -> Path:
    storage = client.app.state.container.settings.storage.dir
    artifact = json.loads(bundle_path(storage, "demo").read_text())
    artifact["source"] = "trained"
    path = bundle_path(storage, "trained")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact))
    return path


def test_models_require_authentication(make_settings: SettingsFactory):
    with TestClient(create_app(make_settings())) as client:
        assert client.get("/api/qop/models?source=demo").status_code == 401
        assert client.get("/api/qop/models/download?source=demo").status_code == 401


def test_demo_is_separate_from_missing_trained_models(client: TestClient):
    trained = client.get("/api/qop/models").json()
    assert trained["available"] is False
    assert trained["source"] == "trained"
    assert "automatic" in trained
    demo = client.get("/api/qop/models?source=demo").json()
    assert demo["source"] == "demo"
    assert {m["name"] for m in demo["models"]} == {"Naive mean", "OLS", "Ridge", "Lasso"}
    assert demo["train_images"] + demo["test_images"] == 120
    download = client.get("/api/qop/models/download?source=demo")
    assert download.status_code == 200
    assert download.json()["source"] == "demo"
    assert client.get("/api/qop/models/download").status_code == 503


def test_demo_predicts_both_modes_without_creating_jobs(client: TestClient):
    response = client.post(
        "/api/qop/predict?source=demo",
        files={"file": ("test.png", make_png(), "image/png")},
        data={"content_type": "anime", "max_size": 2048},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "demo"
    assert (body["width"], body["height"]) == (64, 48)
    assert len(body["predictions"]) == 8
    assert {p["mode"] for p in body["predictions"]} == {"2k", "4k"}
    assert all(0 <= p["value"] <= 1 for p in body["predictions"])
    assert client.get("/api/jobs").json() == []


@pytest.mark.parametrize(
    ("data", "content_type", "max_size", "status"),
    [
        (b"not an image", "anime", 2048, 415),
        (make_png(257, 2), "anime", 2048, 422),
        (make_png(), "other", 2048, 422),
        (make_png(), "anime", 1920, 422),
        (b"x" * (1024 * 1024 + 1), "anime", 2048, 413),
    ],
)
def test_prediction_rejects_invalid_inputs(
    client: TestClient, data, content_type, max_size, status
):
    response = client.post(
        "/api/qop/predict?source=demo",
        files={"file": ("test.png", data, "image/png")},
        data={"content_type": content_type, "max_size": max_size},
    )
    assert response.status_code == status, response.text


def test_real_export_is_reloaded_and_never_falls_back_to_demo(client: TestClient):
    missing = client.post(
        "/api/qop/predict",
        files={"file": ("test.png", make_png(), "image/png")},
        data={"content_type": "anime"},
    )
    assert missing.status_code == 503
    path = install_trained(client)
    assert client.get("/api/qop/models").json()["source"] == "trained"
    path.write_text("{broken JSON")
    assert client.get("/api/qop/models").status_code == 503
    path = install_trained(client)
    artifact = json.loads(path.read_text())
    artifact["source"] = "demo"
    path.write_text(json.dumps(artifact))
    assert client.get("/api/qop/models").status_code == 503


def test_portable_predictor_applies_standardization_and_categories():
    model = Predictor(
        name="example",
        intercept=0.2,
        metrics={},
        terms=[
            Term(feature="input_megapixels", coefficient=0.4, mean=2, scale=2),
            Term(feature="content_type", category="anime", coefficient=0.1, mean=0, scale=1),
        ],
    )
    assert model.predict({"input_megapixels": 4.0, "content_type": "anime"}) == pytest.approx(0.7)
    assert model.predict({"input_megapixels": 4.0, "content_type": "text"}) == pytest.approx(0.6)
