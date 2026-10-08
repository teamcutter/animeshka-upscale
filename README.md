# Animeshka Upscale

AI photo/video upscaler for vintage anime (pre-1980s–90s) — dual Real-ESRGAN inference pipeline with objective + perceptual quality analytics and Grafana dashboard.

> Sprint 1 — Research Memo (GOST) `Research_Memo_Sprint1_GOST.docx` — no custom training; two pretrained Real-ESRGAN (RRDB) models wrapped in a unified inference + analytics stack.

## Overview

Degradation of old anime (film grain, low resolution, analog compression artifacts) is naturally occurring — ideal blind super-resolution case for Real-ESRGAN. The project handles this by:

* **2K mode** — lightweight RRDB generator (reduced RRDB blocks/params) for preview/realtime
* **4K mode** — full RRDB generator (`nf=64, nb=23, gc=32`) for quality mode
* **Unified inference pipeline** — `image|video → model selector (2K/4K) → enhanced output`
* **Analytics module** — PSNR / SSIM / VMAF (where available) + linear regression → predicted subjective score QoP/MOS 1–5 (per Klink et al., r=0.99)
* **Dashboard** — Grafana panels: before/after pairs, objective metrics, QoP, quality-vs-degradation curve, 2K vs 4K speed/compute

Test run (Sprint 1): same 10 anime images + 1 video through both models; metrics + Grafana screenshots.

## Architecture

```
              ┌─────────────────────────────────┐
Client ─────▶ │ FastAPI REST API                │ ───▶ PostgreSQL (jobs, files, metrics)
              │  /api/upscale  /api/metrics      │
              └──────────┬──────────────────────┘
                         │
              ┌──────────▼──────────┐    ┌──────────────────┐
              │ Inference Pipeline  │───▶│ Analytics Module │
              │  RealESRGANUpscaler │    │ PSNR/SSIM/VMAF   │
              │  2K ○──── 4K ●     │    │ LR → QoP/MOS     │
              └──────────┬──────────┘    └────────┬─────────┘
                         │                       │
                    enhanced media          Grafana ──▶ Frontend (before/after + dashboard embed)
```

* **No training from scratch** — pretrained weights reused as-is; second-order degradation robustness (blur → resize → noise → JPEG ×2 + sinc ringing) from Real-ESRGAN (Wang et al., 2021) is leveraged.
* **Efficient 2K path** mirrors Tovar et al. (2023) residual CNN idea: compact model for CPU/realtime, ~same architecture, fewer blocks.

## Real-ESRGAN Inference

### Model

* **RRDBNet**: `in_nc=3, out_nc=3, nf=64, nb=23, gc=32`, `scale=2`, `PixelUnshuffle(2)` → `conv_first` → 23× `RRDB` → `conv_body` → 2× `nearest×2 + conv` → `conv_hr` → `conv_last`, `LeakyReLU(0.2)`
* **RRDB**: 3× `ResidualDenseBlock` + residual scale `0.2`
* **ResidualDenseBlock**: 5 convs with dense concatenation (`nf→gc`, `nf+gc→gc`, … `nf+4gc→nf`), `LeakyReLU(0.2)`, residual `×0.2 + x`
* **Weight**: `weights/upscale_model/RealESRGAN_x2plus.pth` — handles `params_ema` / `params` keys, `weights_only=True`

### Runtime (`RealESRGANUpscaler`)

```python
@dataclass
class UpscalerConfig:
    device: str       # cuda | cpu
    tile_size: int    # 512 default
    model_path: str   # dir containing RealESRGAN
    scale: int = 2
```

* `load_model()` — `cudnn.benchmark=False`, `allow_tf32=True`, `channels_last`, `half()` on CUDA, `eval()`
* `enhance(image: PIL.Image, max_size=1920) -> PIL.Image` — Lanczos downsize if `max(w,h) > max_size//scale`, RGB→BGR→`float32/255`→`torch`, replicate-pad to fixed canvas (`max_size//scale` rounded even) for single-shape CUDA compilation, OOM fallback to `_tile_process`, crop padding, BGR→RGB→PIL
* `_tile_process(img)` — tiled inference with `tile_pad=10`, even-pad for `pixel_unshuffle`, output stitching
* `warmup(max_size=1920)` — dummy canvas pass to pre-compile CUDA kernels behind health-check
* `unload()` — `del model + empty_cache()`
* Video = frame-wise `enhance()` + re-mux via `ffmpeg`

### Libraries

| Lib | Version | Use |
|-----|---------|-----|
| `torch` | 2.5.1 (CUDA 12.1) | RRDB inference |
| `torchvision` | 0.20.1 | |
| `opencv-python-headless` | 4.13.0.90 | color conversion, preproc |
| `pillow` | 12.0.0 | I/O, resize |
| `numpy` | 2.1.1 | tensor/array |
| `fastapi` 0.128 + `uvicorn` 0.40 | — | REST API |
| `pydantic-settings` 2.13 | — | `Settings` + YAML source |
| `pyyaml` 6.0 | — | `config.yml` |
| `prometheus-fastapi-instrumentator` 7.0 | — | metrics |
| `httpx`, `python-multipart` | — | API |
| `sqlalchemy` 2.0 + `alembic` 1.14 | — | ORM + migrations |
| `psycopg` 3 | — | PostgreSQL driver |

> Package manager: **uv**. Dev: `pytest`, `ruff`, `ty`.

## Project Structure

```
animeshka-upscale/
├── backend/                        # Python: API, worker, inference, CLI (uv)
│   ├── src/
│   │   ├── app.py                  # FastAPI factory
│   │   ├── worker.py               # queue worker (python -m src.worker)
│   │   ├── cli.py                  # offline image/video upscale
│   │   ├── container.py            # DI
│   │   ├── core/config.py          # Settings (app/model/upscale/image/log)
│   │   ├── features/
│   │   │   ├── upscale/api/        # POST /upscale, GET /jobs/{id}
│   │   │   └── analytics/          # PSNR/SSIM/VMAF + LR QoP
│   │   ├── infrastructure/
│   │   │   ├── upscale/            # rrdb.py, residual_dense_block.py, upscaler.py
│   │   │   ├── analytics/metrics.py
│   │   │   ├── db/                 # SQLAlchemy engine, models, migrate
│   │   │   └── storage/            # SqlJobRepository, local files
│   │   └── shared/
│   ├── tests/
│   ├── migrations/                 # Alembic (alembic.ini)
│   ├── weights/upscale_model/      # RealESRGAN_x2plus.pth (2K), RealESRGAN_x4plus.pth (4K)
│   ├── config.yml
│   ├── pyproject.toml
│   └── Dockerfile                  # python + uv + ffmpeg
├── frontend/                       # React + TypeScript + Vite + Tailwind (npm)
│   ├── src/
│   ├── public/
│   ├── nginx.conf                  # serves the SPA, proxies /api -> api:8000
│   ├── package.json
│   └── Dockerfile                  # node build -> nginx
├── deploy/grafana/                 # Grafana datasource provisioning
├── docker-compose.yml              # postgres, migrate, api, worker, frontend, grafana
├── docker-compose.gpu.yml          # override: NVIDIA GPU for the worker
└── Research_Memo_Sprint1_GOST.docx
```

Each part has its own README: [backend](backend/README.md), [frontend](frontend/README.md).

## Requirements

* Docker + Docker Compose — enough to run everything
* For local development: Python 3.11–3.12 + [uv](https://docs.astral.sh/uv/) ≥0.4, Node.js 24 + npm
* `ffmpeg` for video remux (optional locally, included in the backend image)
* PostgreSQL 15+ , Grafana 10+ (docker-compose provides)
* NVIDIA GPU with CUDA 12.1+ recommended; CPU fallback works (slow)

## Installation

```bash
git clone <repo> animeshka-upscale
cd animeshka-upscale

# backend (uv)
cd backend && uv sync --group dev && cd ..
# frontend (npm)
cd frontend && npm ci && cd ..
```

### Weights

```bash
mkdir -p backend/weights/upscale_model
curl -L -o backend/weights/upscale_model/RealESRGAN_x2plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth
# 4K variant (x4) — same API, scale=4
curl -L -o backend/weights/upscale_model/RealESRGAN_x4plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth

# or 2K lightweight — distilled / fewer nb (place as backend/weights/upscale_2k/)
```

### Docker

Full stack (PostgreSQL + migrations + API + worker + frontend + Grafana):

```bash
docker compose up --build     # UI :8080, API :8000, Grafana :3000 (admin/admin), PostgreSQL :5432
docker compose up -d postgres # only the database, run backend/frontend locally
# worker on an NVIDIA GPU (nvidia-container-toolkit):
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

A mode is available only if its weight file exists in `upscale.model_path`
(`RealESRGAN_x2plus.pth` for `2k`, `RealESRGAN_x4plus.pth` for `4k`). A missing file disables that
mode instead of failing startup: `/health` reports `"modes": {"2k": true, "4k": false}`, uploads
with a disabled mode get `422`, and the UI greys the option out.

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"ok","backend":"realesrgan","worker":"embedded","modes":{"2k":true,"4k":false}}
```

#### macOS (Apple Silicon)

Docker Desktop, OrbStack or Podman all work; the images are linux/arm64 and the worker runs the
model on CPU (no GPU passthrough on macOS, so leave `docker-compose.gpu.yml` out). CUDA wheels only
exist for x86_64; `backend/pyproject.toml` pins the CUDA index to that architecture and arm64 falls
back to the CPU wheels from PyPI.

```bash
# Podman: the VM needs more than the default memory for torch
podman machine set --memory 8192 && podman machine start
echo "UPSCALE__BACKEND=realesrgan" > backend/.env
podman compose up --build            # same compose file; uses docker-compose under the hood
```

`migrate` applies Alembic migrations once, then `api` (queues jobs) and `worker` (runs the model)
start; `frontend` is nginx serving the built SPA and proxying `/api` to `api`, so the UI at
http://localhost:8080 needs no CORS. `backend/data` and `backend/weights` are mounted into the
backend containers; `backend/.env` is picked up if present.

## Configuration

`backend/config.yml` + `backend/.env` (env overrides YAML, `__` nesting):

```yaml
# config.yml
upscale:
  backend: stub      # stub (Lanczos, no weights) | realesrgan
  model_path: ./weights/upscale_model
  tile_size: 512
  device: auto       # auto|cuda|mps|cpu
image:
  max_size_mb: 10
  max_width: 2048
  max_height: 2048
database:
  url: sqlite:///./data/animeshka.db   # postgresql://user:pass@host:5432/db
  auto_migrate: true                   # run Alembic on startup
worker:
  embedded: true     # true: API runs jobs itself; false: run `python -m src.worker`
  poll_interval: 1.0
log:
  level: INFO
```

```bash
# .env (see .env.example)
UPSCALE__BACKEND=realesrgan
DATABASE__URL=postgresql://animeshka:animeshka@localhost:5432/animeshka
WORKER__EMBEDDED=false
```

## Usage

Backend commands (`uv run ...`) run from `backend/`, frontend commands (`npm ...`) from `frontend/`.

### Run API

```bash
cd backend
uv run uvicorn src.app:create_app --factory --reload --port 8000
# Swagger: http://localhost:8000/docs
```

Defaults need nothing else: SQLite in `backend/data/animeshka.db`, jobs run inside the API process.

### Run frontend

```bash
cd frontend
npm run dev    # http://localhost:5173, /api is proxied to the API on :8000
```

The UI talks to the API only through relative URLs (`frontend/src/api.ts`). The header badge reads
`/health` (active backend, available modes); the main tab does `POST /api/upscale` (or
`/api/upscale/video`) → polls `GET /api/jobs/{id}` until `done|failed` → shows the original (kept in
the browser) against `GET /api/jobs/{id}/result` in the before/after slider; the history tab lists
`GET /api/jobs` with result thumbnails and downloads.

### Run with PostgreSQL and a separate worker

```bash
docker compose up -d postgres
# .env: DATABASE__URL=postgresql://animeshka:animeshka@localhost:5432/animeshka
#       WORKER__EMBEDDED=false
uv run alembic upgrade head          # or rely on DATABASE__AUTO_MIGRATE=true
uv run uvicorn src.app:create_app --factory --port 8000   # terminal 1: API, only queues jobs
uv run python -m src.worker                               # terminal 2: worker, runs the model
```

Job lifecycle: `queued` → `processing` → `done | failed`. The worker claims jobs atomically
(`UPDATE ... WHERE status='queued'`, `FOR UPDATE SKIP LOCKED` on PostgreSQL), so several workers
can run in parallel.

### Database

Tables (`migrations/versions/`): `jobs` (status, mode, kind, timestamps), `files` (input/output
path, size, resolution), `metrics` (`job_id`, `name`, `value`, e.g. `processing_seconds`;
analytics adds PSNR/SSIM/QoP here). Grafana reads them through the provisioned PostgreSQL
datasource.

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add column"   # after changing backend/src/infrastructure/db/models.py
uv run alembic downgrade -1
```

> Video jobs are accepted and stored but not processed yet (frame-wise pipeline lives in `backend/src/cli.py`).

### API

```bash
# image 2K
curl -X POST http://localhost:8000/api/upscale \
  -F "file=@input.jpg" -F "mode=2k" | jq

# image 4K, output long side <= 2048
curl -X POST http://localhost:8000/api/upscale \
  -F "file=@input.jpg" -F "mode=4k" -F "max_size=2048"

# video
curl -X POST http://localhost:8000/api/upscale/video \
  -F "file=@clip.mp4" -F "mode=4k"

# job status (+ input/output resolution and metrics)
curl http://localhost:8000/api/jobs/<id>

# history, newest first
curl "http://localhost:8000/api/jobs?status=done&limit=20&offset=0"
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upscale` | POST | Image upscale (`file`, `mode=2k|4k`, `max_size`) |
| `/api/upscale/video` | POST | Video upscale (frame-wise) |
| `/api/jobs` | GET | Job history (`status`, `limit`, `offset`) |
| `/api/jobs/{id}` | GET | Job status + metrics |
| `/api/jobs/{id}/result` | GET | Download upscaled file (when `done`) |
| `/api/metrics` | GET | Prometheus metrics |
| `/health` | GET | Health check (503 if the database is down) + `modes` available on this server |
| `/docs` | GET | Swagger UI |


## Analytics & Dashboard

* **Objective**: PSNR, SSIM (scikit-image / pyiqa), VMAF (`libvmaf` if available) before/after
* **Subjective**: linear regression on 32 metric features → QoP/MOS 1–5 (sprint 1 model from Maksim)
* **Grafana**: data source = PostgreSQL / Prometheus; panels — before/after, metric tables, QoP gauge, degradation-vs-quality line, 2K vs 4K latency/FLOPs bar
* Test dataset (Banum): vintage anime stills — natural degradation, no synthetic blur

## Team (Sprint 1, 01.09–14.09.2026)

| Member | Role | Ownership |
|--------|------|-----------|
| Banum | Data Engineer | dataset, metrics/LR QoP, Grafana assembly, docs |
| Gleb | Backend | FastAPI, PostgreSQL, backend↔inference wiring |
| Ruslan | Backend (inference) | unified 2K/4K `RealESRGANUpscaler`, Grafana local run, 10+1 test pass |
| Maksim | Frontend | before/after UI, dashboard embed, API integration |

## Git Workflow

Single-branch trunk: `main` is `master`. No `develop`. All work via short-lived feature branches + PR into `main`.

```
main (master) ──●──●──●──────────●──●──●──  (protected)
                 \        \      /        \
feature/foo ──────●──●──●──●────●          ●──●  → PR → main
fix/bar   ─────────────●──●──●──●
```

Rules:

* Branch from `main`, PR back to `main` — no long-lived branches.
* Naming: `feature/<short>`, `fix/<short>`, `docs/<short>`, `chore/<short>` (e.g. `feature/upscaler-tile-fallback`).
* PR requirements: backend `ruff check` + `ty check` + `pytest` and frontend `npm run lint` + `npm run build` green, 1 approval, squash-merge. Delete branch after merge.
* Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
* Never push directly to `main`; keep `main` deployable.

```bash
git checkout main && git pull
git checkout -b feature/my-change
# ... work ...
(cd backend && uv run ruff check src tests migrations && uv run ty check src tests && uv run pytest -v)
(cd frontend && npm run lint && npm run build)
git push -u origin feature/my-change
# open PR: feature/my-change → main
```

## Development

```bash
# backend/
uv run ruff check src tests migrations
uv run ruff format src tests migrations
uv run ty check src tests
uv run pytest -v                                   # SQLite in a temp dir
TEST_DATABASE_URL=postgresql://animeshka:animeshka@localhost:5432/animeshka_test uv run pytest -v

# frontend/
npm run lint
npm run build
```

CI (`.github/workflows/ci.yml`) has two jobs: `backend` runs the suite twice (SQLite and a
PostgreSQL service), `frontend` lints and builds the app.

## References

1. Wang X. et al. Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic Data. arXiv:2107.10833, 2021.
2. Tovar N. et al. Image Upscaling with Deep Machine Learning for Energy-Efficient Data Communications. Electronics 12(3):689, 2023.
3. Klink J. et al. Video Quality Modelling — Classical vs ML. Applied Sciences 14(16):7029, 2024.
4. CyberLeninka — DL image enhancement survey (Banum source).

## License

MIT — see [LICENSE](LICENSE).
