"""Background training uses the API's configured database, for SQLite and PostgreSQL."""

import hashlib
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread

from sqlalchemy.orm import Session, sessionmaker

from src.core.config import QopSettings
from src.features.qop.dataset import collect
from src.features.qop.models import ModelBundle
from src.features.qop.service import ModelsUnavailableError, bundle_path, load_models
from src.features.upscale.domain import now_utc

logger = logging.getLogger(__name__)


class AutomaticQop:
    def __init__(self, sessions: sessionmaker[Session], storage: Path, settings: QopSettings):
        self.sessions, self.storage, self.settings = sessions, storage, settings
        self._stop, self._wake = Event(), Event()
        self._lock, self._refresh_lock = Lock(), Lock()
        self._thread: Thread | None = None
        self._status: dict = {
            "state": "pending" if settings.enabled else "disabled",
            "completed_images": 0,
            "usable_jobs": 0,
            "distinct_images": 0,
            "missing_quality": 0,
            "missing_files": 0,
            "backfilled_jobs": 0,
            "min_images": settings.min_images,
            "last_checked": None,
            "last_trained": None,
        }

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def _update(self, **values) -> None:
        with self._lock:
            self._status.update(values)

    def start(self) -> None:
        if not self.settings.enabled or self._thread is not None:
            return
        self._thread = Thread(target=self._loop, name="qop-training", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def request_refresh(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            self.refresh()
            self._wake.wait(self.settings.poll_interval)

    def refresh(self) -> None:
        if not self.settings.enabled or not self._refresh_lock.acquire(blocking=False):
            return
        try:
            self._update(state="collecting", error=None)
            dataset = collect(self.sessions, self.storage, self._stop)
            self._update(
                completed_images=dataset.completed_images,
                usable_jobs=len(dataset.records),
                distinct_images=dataset.distinct_images,
                missing_quality=dataset.missing_quality,
                missing_files=dataset.missing_files,
                backfilled_jobs=dataset.backfilled_jobs,
                last_checked=now_utc().isoformat(),
            )
            if self._stop.is_set():
                return
            if dataset.distinct_images < self.settings.min_images:
                self._update(state="insufficient_data")
                return
            # Ignore speed/timing metrics: only changes to the training data need a new fit.
            columns = [
                "job_id",
                "filename",
                "mode",
                "max_size",
                "width",
                "height",
                "input_bytes",
                "input_megapixels",
                "psnr_db",
                "ssim",
                "sharpness_input",
                "sharpness_bicubic",
                "sharpness_output",
            ]
            fingerprint = hashlib.sha256(
                json.dumps(
                    [{k: row[k] for k in columns} for row in dataset.records],
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            try:
                current = load_models(self.storage, "trained")
            except ModelsUnavailableError:
                current = None
            if current is not None and current.dataset_fingerprint == fingerprint:
                self._update(state="ready", last_trained=current.created_at.isoformat())
                return
            self._update(state="training")
            # Heavy imports and fitting run only here, outside request handling/startup.
            import pandas as pd

            from src.features.qop.training import run

            destination = bundle_path(self.storage, "trained")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=".training-", dir=destination.parent) as temp:
                run(pd.DataFrame(dataset.records), "qop", Path(temp), 5, reports=False)
                path = Path(temp) / "models.json"
                model = ModelBundle.model_validate_json(path.read_text())
                model.dataset_fingerprint = fingerprint
                path.write_text(model.model_dump_json(indent=2))
                if self._stop.is_set():
                    return
                # Keep serving the previous complete model until the new fit succeeds.
                path.replace(destination)
            self._update(state="ready", last_trained=model.created_at.isoformat())
        except Exception:
            logger.exception("Automatic QoP update failed")
            self._update(state="error", error="Unable to update models from saved job metrics.")
        finally:
            self._refresh_lock.release()
