# Animeshka Upscale — backend

FastAPI API, job worker, Real-ESRGAN inference and CLI. See the [project README](../README.md)
for the architecture, configuration and API reference.

All commands run from this directory (`backend/`):

```bash
uv sync --group dev

uv run uvicorn src.app:create_app --factory --reload --port 8000   # API, Swagger at /docs
uv run python -m src.worker                                        # worker (WORKER__EMBEDDED=false)
uv run python -m src.cli input.png --scale 2                       # offline image/video upscale

# Prometheus business metrics: API at http://localhost:8000/api/metrics,
# worker at http://localhost:9101/metrics (METRICS__WORKER_PORT). Grafana reads
# both via Prometheus plus the PostgreSQL `metrics` table; see deploy/.

uv run alembic upgrade head
uv run ruff check src tests migrations
uv run ruff format src tests migrations
uv run ty check src tests
uv run pytest -v
```

`config.yml`, `.env`, `weights/` and `data/` are resolved relative to this directory.

From the repository root, `bash scripts/run-stack.sh` detects macOS and starts a native MPS bridge
before starting the container stack. The container worker uses the bridge for image/video frames,
with local CPU fallback when unavailable. Start only the bridge with
`bash scripts/start-mps-bridge.sh`; its token, log and PID are in `backend/data/mps-bridge.*`.
On other hosts the launcher starts the regular container stack. The offline CLI also supports
`--device mps`, falling back to CPU when MPS is unavailable.

Video uploads require FFmpeg with H.264 (`libx264`) and AAC encoders on the worker's PATH.
Docker includes it; install locally with `brew install ffmpeg` (macOS) or
`sudo apt-get install ffmpeg` (Debian/Ubuntu). The video integration tests use FFmpeg/ffprobe
to verify the resulting MP4 streams and audio; they skip if either tool is unavailable.
