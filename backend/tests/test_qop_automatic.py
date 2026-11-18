from io import BytesIO
from pathlib import Path
from threading import Event

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, select

from src.features.qop.automatic import AutomaticQop
from src.features.qop.dataset import QUALITY_NAMES, collect
from src.features.qop.service import bundle_path
from src.infrastructure.db.engine import create_session_factory
from src.infrastructure.db.models import FileRow, MetricRow


def add_images(client: TestClient, count: int, *, first: int = 0) -> None:
    rng = np.random.default_rng(42 + first)
    for i in range(first, first + count):
        pixels = rng.integers(0, 256, (24 + i, 32 + i, 3), dtype=np.uint8)
        buffer = BytesIO()
        Image.fromarray(pixels).save(buffer, format="PNG")
        response = client.post(
            "/api/upscale",
            files={"file": (f"source-{i}.png", buffer.getvalue(), "image/png")},
            data={"mode": "4k" if i % 2 else "2k"},
        )
        assert response.status_code == 202, response.text


def trainer(client: TestClient) -> AutomaticQop:
    container = client.app.state.container
    # Deterministic refreshes exercise the same code as the background loop.
    container.qop.stop()
    return AutomaticQop(
        create_session_factory(container.engine),
        container.settings.storage.dir,
        container.settings.qop,
    )


def test_old_jobs_are_backfilled_without_running_upscaler(client: TestClient, monkeypatch):
    automatic = trainer(client)
    add_images(client, 2)
    with automatic.sessions.begin() as session:
        session.execute(delete(MetricRow).where(MetricRow.name.in_(QUALITY_NAMES)))
        # Resolve media persisted by a container through the configured data mount.
        for file in session.scalars(select(FileRow)):
            file.path = str(
                Path("/app/data")
                / ("inputs" if file.role == "input" else "outputs")
                / Path(file.path).name
            )

    def no_inference(*args, **kwargs):
        raise AssertionError("Backfill must use the saved output, not run inference")

    for upscaler in client.app.state.container.upscalers.values():
        monkeypatch.setattr(upscaler, "enhance", no_inference)
    automatic.refresh()
    status = automatic.status()
    assert status["state"] == "insufficient_data"
    assert status["completed_images"] == status["usable_jobs"] == 2
    assert status["backfilled_jobs"] == 2
    with automatic.sessions() as session:
        assert (
            len(list(session.scalars(select(MetricRow).where(MetricRow.name.in_(QUALITY_NAMES)))))
            == 10
        )
    assert collect(automatic.sessions, automatic.storage).backfilled_jobs == 0


def test_missing_media_is_reported_without_breaking_collection(client: TestClient):
    automatic = trainer(client)
    add_images(client, 1)
    with automatic.sessions.begin() as session:
        session.execute(delete(MetricRow).where(MetricRow.name.in_(QUALITY_NAMES)))
        for file in session.scalars(select(FileRow).where(FileRow.role == "output")):
            file.path = "/missing/output.png"
    automatic.refresh()
    status = automatic.status()
    assert status["state"] == "insufficient_data"
    assert status["missing_quality"] == status["missing_files"] == 1
    assert status["usable_jobs"] == 0


def test_training_uses_saved_metrics_and_only_retrains_after_changes(client: TestClient):
    automatic = trainer(client)
    add_images(client, 12)
    automatic.refresh()
    assert automatic.status()["state"] == "ready"
    path = bundle_path(automatic.storage, "trained")
    first = path.read_bytes()
    client.app.state.container.qop = automatic
    catalog = client.get("/api/qop/models").json()
    assert catalog["source"] == "trained"
    assert catalog["rows"] == 12
    assert catalog["dataset_fingerprint"]
    assert len(catalog["models"]) == 4
    automatic.refresh()
    assert path.read_bytes() == first
    add_images(client, 1, first=12)
    automatic.refresh()
    assert path.read_bytes() != first
    assert client.get("/api/qop/models").json()["rows"] == 13


def test_failed_retraining_keeps_previous_model(client: TestClient, monkeypatch):
    from src.features.qop import training

    automatic = trainer(client)
    add_images(client, 12)
    automatic.refresh()
    path = bundle_path(automatic.storage, "trained")
    first = path.read_bytes()
    add_images(client, 1, first=12)

    def fail(*args, **kwargs):
        raise RuntimeError("training failed")

    monkeypatch.setattr(training, "run", fail)
    automatic.refresh()
    assert automatic.status()["state"] == "error"
    assert path.read_bytes() == first


def test_background_loop_reads_existing_database_on_start(client: TestClient, monkeypatch):
    automatic = trainer(client)
    add_images(client, 1)
    checked = Event()
    original = automatic.refresh

    def refresh():
        original()
        checked.set()

    monkeypatch.setattr(automatic, "refresh", refresh)
    automatic.start()
    try:
        assert checked.wait(10), "The background updater did not inspect the database"
        assert automatic.status()["completed_images"] == 1
    finally:
        automatic.stop()
