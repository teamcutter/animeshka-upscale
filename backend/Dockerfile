FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg/ffprobe: video re-mux (audio track) for the video pipeline.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so code changes don't reinstall torch.
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

COPY alembic.ini config.yml ./
COPY migrations ./migrations
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "src.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
