# Animeshka Upscale — backend

FastAPI API, job worker, Real-ESRGAN inference and CLI. See the [project README](../README.md)
for the architecture, configuration and API reference.

All commands run from this directory (`backend/`):

```bash
uv sync --group dev

uv run uvicorn src.app:create_app --factory --reload --port 8000   # API, Swagger at /docs
uv run python -m src.worker                                        # worker (WORKER__EMBEDDED=false)
uv run python -m src.cli input.png --scale 2                       # offline image/video upscale

uv run alembic upgrade head
uv run ruff check src tests migrations
uv run ruff format src tests migrations
uv run ty check src tests
uv run pytest -v
```

`config.yml`, `.env`, `weights/` and `data/` are resolved relative to this directory.
