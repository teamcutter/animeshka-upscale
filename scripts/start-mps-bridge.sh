#!/usr/bin/env bash
set -eu
repo_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root/backend"
python_bin="${MPS_WORKER_PYTHON:-$PWD/.venv/bin/python}"
if [ ! -x "$python_bin" ]; then
    echo 'Create the backend environment first: cd backend && uv sync --group dev' >&2
    exit 1
fi
export STORAGE__DIR="${STORAGE__DIR:-$PWD/data}"
export UPSCALE__DEVICE=mps
export UPSCALE__BACKEND=realesrgan
mkdir -p "$STORAGE__DIR"
if ! "$python_bin" -c 'import torch; raise SystemExit(0 if torch.backends.mps.is_available() else 1)'; then
    echo 'MPS is unavailable; the container worker will use CPU fallback.' >&2
    exit 0
fi
check_bridge() {
    "$python_bin" -c 'import json,urllib.request; s=json.load(urllib.request.urlopen("http://127.0.0.1:8766/health",timeout=1)); assert s.get("service")=="animeshka-mps" and s.get("device")=="mps"' 2>/dev/null
}
if check_bridge; then
    echo 'MPS bridge is already running on port 8766.'
    exit 0
fi
nohup "$python_bin" -m src.mps_bridge > "$STORAGE__DIR/mps-bridge.log" 2>&1 < /dev/null &
bridge_pid=$!
echo "$bridge_pid" > "$STORAGE__DIR/mps-bridge.pid"
for attempt in $(seq 1 20); do
    if check_bridge; then
        echo "MPS bridge ready on port 8766 (PID $bridge_pid)."
        exit 0
    fi
    if ! kill -0 "$bridge_pid" 2>/dev/null; then
        echo "MPS bridge failed; see $STORAGE__DIR/mps-bridge.log" >&2
        exit 1
    fi
    sleep 1
done
echo "MPS bridge startup timed out; see $STORAGE__DIR/mps-bridge.log" >&2
exit 1
