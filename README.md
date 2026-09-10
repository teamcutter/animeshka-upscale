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

> Package manager: **uv**. Dev: `pytest`, `ruff`, `ty`.

## Project Structure

```
animeshka-upscale/
├── src/
│   ├── app.py                  # FastAPI factory
│   ├── container.py            # DI
│   ├── core/config.py          # Settings (app/model/upscale/image/log)
│   ├── features/
│   │   ├── upscale/api/        # POST /upscale, GET /jobs/{id}
│   │   └── analytics/          # PSNR/SSIM/VMAF + LR QoP
│   ├── infrastructure/
│   │   ├── upscale/            # rrdb.py, residual_dense_block.py, upscaler.py
│   │   ├── analytics/metrics.py
│   │   └── storage/            # PostgreSQL
│   └── shared/
├── weights/
│   ├── upscale_2k/RealESRGAN_x2plus.pth   # lightweight
│   └── upscale_4k/RealESRGAN_x4plus.pth   # full
├── config.yml
├── pyproject.toml              # uv
├── docker-compose.yml
├── docker-compose.cpu.yml
└── Research_Memo_Sprint1_GOST.docx
```

## Requirements

* Python 3.11–3.12, [uv](https://docs.astral.sh/uv/) ≥0.4
* `ffmpeg` for video remux (optional)
* PostgreSQL 15+ , Grafana 10+ (docker-compose provides)
* NVIDIA GPU with CUDA 12.1+ recommended; CPU fallback works (slow)

## Installation

```bash
git clone <repo> animeshka-upscale
cd animeshka-upscale

# create env + install (uv)
uv sync
# with dev deps
uv sync --group dev

# activate
source .venv/bin/activate  # or uv run <cmd>
```

### Weights

```bash
mkdir -p weights/upscale_model
curl -L -o weights/upscale_model/RealESRGAN_x2plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth
# 4K variant (x4) — same API, scale=4
curl -L -o weights/upscale_model/RealESRGAN_x4plus.pth \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x4plus.pth

# or 2K lightweight — distilled / fewer nb (place as weights/upscale_2k/)
```

Grafana + Postgres via Docker:

```bash
docker compose up --build          # GPU (CUDA)
docker compose -f docker-compose.cpu.yml up --build  # CPU
```

## Configuration

`config.yml` + `.env` (env overrides YAML, `__` nesting):

```yaml
# config.yml
upscale:
  model_path: ./weights/upscale_model
  tile_size: 512
  device: cuda        # cuda|cpu
image:
  max_size_mb: 10
  max_width: 2048
  max_height: 2048
log:
  level: INFO
```

```bash
# .env
APP__PORT=8000
UPSCALE__DEVICE=cuda
UPSCALE__TILE_SIZE=512
DATABASE_URL=postgresql://user:pass@localhost:5432/animeshka
```

## Usage

### API

```bash
# image 2K
curl -X POST http://localhost:8000/api/upscale \
  -F "file=@input.jpg" -F "mode=2k" | jq

# image 4K + metrics
curl -X POST http://localhost:8000/api/upscale \
  -F "file=@input.jpg" -F "mode=4k" -F "with_metrics=true"

# video
curl -X POST http://localhost:8000/api/upscale/video \
  -F "file=@clip.mp4" -F "mode=4k"

# job status
curl http://localhost:8000/api/jobs/<id>
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upscale` | POST | Image upscale (`file`, `mode=2k|4k`, `max_size`) |
| `/api/upscale/video` | POST | Video upscale (frame-wise) |
| `/api/jobs/{id}` | GET | Job status + metrics |
| `/api/metrics` | GET | Prometheus metrics |
| `/health` | GET | Health check |
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
* PR requirements: `uv run ruff check` + `ty check` + `pytest` green, 1 approval, squash-merge. Delete branch after merge.
* Commit style: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
* Never push directly to `main`; keep `main` deployable.

```bash
git checkout main && git pull
git checkout -b feature/my-change
# ... work ...
uv run ruff check src/ && uv run ty check && uv run pytest -v
git push -u origin feature/my-change
# open PR: feature/my-change → main
```

## Development

```bash
uv run ruff check src/
uv run ruff format src/
uv run ty check
uv run pytest -v
```

## References

1. Wang X. et al. Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic Data. arXiv:2107.10833, 2021.
2. Tovar N. et al. Image Upscaling with Deep Machine Learning for Energy-Efficient Data Communications. Electronics 12(3):689, 2023.
3. Klink J. et al. Video Quality Modelling — Classical vs ML. Applied Sciences 14(16):7029, 2024.
4. CyberLeninka — DL image enhancement survey (Banum source).

## License

MIT — see [LICENSE](LICENSE).
