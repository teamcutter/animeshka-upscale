"""Read the application's existing jobs and recover old quality metrics from saved media."""

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.features.upscale.domain import now_utc
from src.features.upscale.quality import quality_metrics, sharpness
from src.features.upscale.service import fit_to_output
from src.infrastructure.db.models import JobRow, MetricRow

logger = logging.getLogger(__name__)
QUALITY_NAMES = ("psnr_db", "ssim", "sharpness_bicubic", "sharpness_output", "sharpness_input")


@dataclass
class Dataset:
    records: list[dict[str, Any]]
    completed_images: int = 0
    missing_quality: int = 0
    missing_files: int = 0
    backfilled_jobs: int = 0

    @property
    def distinct_images(self) -> int:
        return len({r["filename"] for r in self.records})


def media_path(saved: str, storage: Path, role: str) -> Path:
    path = Path(saved)
    if path.is_file():
        return path
    # A container's /app/data path may be read from a host using the same data mount.
    return storage / ("inputs" if role == "input" else "outputs") / path.name


def save_metrics(sessions: sessionmaker[Session], job_id: UUID, values: dict[str, float]) -> None:
    with sessions.begin() as session:
        job = session.get(JobRow, job_id)
        if job is None or job.status != "done":
            return
        existing = {m.name: m for m in job.metrics}
        for name, value in values.items():
            if name in existing:
                if not math.isfinite(existing[name].value):
                    existing[name].value = value
            else:
                job.metrics.append(MetricRow(name=name, value=value, created_at=now_utc()))


def collect(
    sessions: sessionmaker[Session],
    storage: Path,
    stop: Event | None = None,
) -> Dataset:
    # Finish the read transaction before opening image files or writing backfilled metrics.
    with sessions() as session:
        jobs = list(
            session.scalars(
                select(JobRow)
                .where(
                    JobRow.kind == "image",
                    JobRow.status == "done",
                )
                .order_by(JobRow.id)
            )
        )
        snapshot = []
        for job in jobs:
            files = {f.role: f for f in job.files}
            source, output = files.get("input"), files.get("output")
            snapshot.append(
                (
                    job.id,
                    {
                        "filename": job.original_filename,
                        "mode": job.mode,
                        "max_size": job.max_size,
                        "width": source.width if source else None,
                        "height": source.height if source else None,
                        "input_bytes": source.size_bytes if source else 0,
                        **{m.name: m.value for m in job.metrics},
                    },
                    source.path if source else None,
                    output.path if output else None,
                )
            )

    dataset = Dataset(records=[], completed_images=len(snapshot))
    for job_id, row, input_path, output_path in snapshot:
        if stop is not None and stop.is_set():
            break
        missing = [
            name for name in QUALITY_NAMES if name not in row or not math.isfinite(row[name])
        ]
        if missing:
            try:
                if input_path is None:
                    raise FileNotFoundError
                with Image.open(media_path(input_path, storage, "input")) as original:
                    row["width"], row["height"] = original.size
                    source = fit_to_output(
                        original.convert("RGB"), row["max_size"], 4 if row["mode"] == "4k" else 2
                    )
                if missing == ["sharpness_input"]:
                    measured = {
                        "sharpness_input": round(
                            sharpness(np.asarray(source.convert("L"), dtype=np.float64)), 4
                        )
                    }
                else:
                    if output_path is None:
                        raise FileNotFoundError
                    with Image.open(media_path(output_path, storage, "output")) as output:
                        measured = quality_metrics(source, output.convert("RGB"))
                save_metrics(sessions, job_id, measured)
                row.update({name: measured[name] for name in missing})
                dataset.backfilled_jobs += 1
            except (FileNotFoundError, OSError, Image.DecompressionBombError):
                dataset.missing_files += 1
                dataset.missing_quality += 1
                continue
            except Exception:
                logger.exception("Cannot recover quality metrics for job %s", job_id)
                dataset.missing_quality += 1
                continue
        if not row.get("width") or not row.get("height") or not row["input_bytes"]:
            continue
        if row["sharpness_bicubic"] <= 0:
            continue
        row.setdefault("input_megapixels", round(row["width"] * row["height"] / 1e6, 4))
        row["content_type"] = "unknown"
        row["job_id"] = str(job_id)
        dataset.records.append(row)
    return dataset
