#!/usr/bin/env bash
set -eu

repo_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ -n "${CONTAINER_ENGINE:-}" ]; then
    engine="$CONTAINER_ENGINE"
elif command -v podman >/dev/null 2>&1; then
    engine=podman
else
    engine=docker
fi

if [ "$(uname -s)" = Darwin ]; then
    # Keep queue processing in Docker; the host bridge supplies Metal inference.
    python_bin="${MPS_WORKER_PYTHON:-$repo_root/backend/.venv/bin/python}"
    if [ ! -x "$python_bin" ]; then
        echo 'Create the backend environment first: cd backend && uv sync --group dev' >&2
        exit 1
    fi
    bash scripts/start-mps-bridge.sh
    exec "$engine" compose up --build "$@"
else
    exec "$engine" compose up --build "$@"
fi
