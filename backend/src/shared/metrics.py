"""Prometheus business metrics for the upscale pipeline.

These live in the default ``prometheus_client`` registry, so the API serves them
next to the HTTP metrics from ``prometheus-fastapi-instrumentator`` on
``/api/metrics`` and the worker serves them on its own ``/metrics`` port.

Everything is measured per finished job: how long a photo or a video frame took,
how big the input and the output were, and the resulting throughput in
megapixels per second.
"""

import logging

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Latency buckets in seconds, from a small 2K frame on a fast GPU to a large
# 4K frame on CPU.
DURATION_BUCKETS = (0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300)
MEGAPIXEL_BUCKETS = (0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64)
BYTE_BUCKETS = (
    64 * 1024,
    256 * 1024,
    1024**2,
    4 * 1024**2,
    16 * 1024**2,
    64 * 1024**2,
    256 * 1024**2,
)
THROUGHPUT_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)

KIND = "kind"
MODE = "mode"
STATUS = "status"

JOBS_TOTAL = Counter(
    "upscale_jobs_total",
    "Upscale jobs by media kind, mode and final status.",
    [KIND, MODE, STATUS],
)

JOBS_IN_PROGRESS = Gauge(
    "upscale_jobs_in_progress",
    "Jobs currently being processed.",
    [KIND],
)

JOB_DURATION_SECONDS = Histogram(
    "upscale_job_duration_seconds",
    "Wall-clock time to process one job.",
    [KIND, MODE],
    buckets=DURATION_BUCKETS,
)

INPUT_BYTES = Histogram(
    "upscale_input_bytes",
    "Size of the uploaded media in bytes.",
    [KIND],
    buckets=BYTE_BUCKETS,
)

OUTPUT_BYTES = Histogram(
    "upscale_output_bytes",
    "Size of the produced media in bytes.",
    [KIND],
    buckets=BYTE_BUCKETS,
)

INPUT_MEGAPIXELS = Histogram(
    "upscale_input_megapixels",
    "Input media size in megapixels.",
    [KIND],
    buckets=MEGAPIXEL_BUCKETS,
)

OUTPUT_MEGAPIXELS = Histogram(
    "upscale_output_megapixels",
    "Output media size in megapixels.",
    [KIND],
    buckets=MEGAPIXEL_BUCKETS,
)

MEGAPIXELS_PER_SECOND = Histogram(
    "upscale_megapixels_per_second",
    "Output megapixels produced per second (throughput).",
    [KIND, MODE],
    buckets=THROUGHPUT_BUCKETS,
)

_worker_metrics_started = False


def start_worker_metrics_server(port: int) -> None:
    """Expose this process's metrics over HTTP.

    The API already answers on ``/api/metrics``; the worker has no HTTP server of
    its own, so Prometheus scrapes the worker on this port instead. Safe to call
    more than once: only the first call starts the server.
    """
    global _worker_metrics_started
    if _worker_metrics_started:
        return
    try:
        start_http_server(port)
    except OSError:
        logger.warning("Could not start the metrics server on port %d", port, exc_info=True)
        return
    _worker_metrics_started = True
    logger.info("Worker metrics exposed on :%d/metrics", port)


def observe_job(
    *,
    kind: str,
    mode: str,
    status: str,
    duration_seconds: float,
    input_bytes: int,
    output_bytes: int | None,
    input_megapixels: float | None,
    output_megapixels: float | None,
    megapixels_per_second: float | None,
) -> None:
    """Record all per-job metrics in one call."""
    JOBS_TOTAL.labels(kind=kind, mode=mode, status=status).inc()
    JOB_DURATION_SECONDS.labels(kind=kind, mode=mode).observe(duration_seconds)
    INPUT_BYTES.labels(kind=kind).observe(input_bytes)
    if input_megapixels is not None:
        INPUT_MEGAPIXELS.labels(kind=kind).observe(input_megapixels)
    if output_bytes is not None:
        OUTPUT_BYTES.labels(kind=kind).observe(output_bytes)
    if output_megapixels is not None:
        OUTPUT_MEGAPIXELS.labels(kind=kind).observe(output_megapixels)
    if megapixels_per_second is not None:
        MEGAPIXELS_PER_SECOND.labels(kind=kind, mode=mode).observe(megapixels_per_second)
