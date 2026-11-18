# Analytics: dataset, indicators and the QoP regression (Sprints 5–6)

Methodology: research memo of Sprint 5. The model predicts the quality of an upscale **before**
it runs, from the input file and the settings.

```
QoP = 0.4·norm(PSNR) + 0.4·SSIM + 0.2·norm(sharpness_output / sharpness_bicubic)
```

`norm()` is min-max scaling to 0..1 fitted on the training split. Backup target: `psnr_db`.
All runs of the same source filename stay in the same train/test or cross-validation fold;
target normalization is fitted again inside each training fold.

| File | What it does |
|---|---|
| `run_dataset.py` | uploads a folder of images through the running app in 2K and 4K |
| `export_features.sql` | one row per finished image job: input features + quality metrics |
| `dataset/content_types.example.csv` | template for manual `content_type` labels (anime, portrait, landscape, text, noise) |
| `qop_regression.py` | EDA, QoP target, OLS vs Ridge vs Lasso vs naive mean, R2 / adj. R2 / MAE / RMSE, k-fold CV, VIF, plots |

Features (input side only, no output metrics → no data leakage): `input_megapixels`,
`mode_4k`, `log(input_bytes)`, `log(sharpness_input)`, aspect ratio, `max_size`,
`content_type` (one-hot). Constant features are omitted. Historical CSVs without `max_size`
assume the dataset runner's default of 2048; supply the real values if they differed.

## Automatic database integration

Start the normal app and open **Модели → Обученные модели**. The API uses its own
configured `DATABASE__URL` (SQLite locally, PostgreSQL in Compose) and checks completed
image jobs every 30 seconds. No CSV export or separate training command is needed.

The automatic flow:

1. Reads image dimensions, file sizes, modes, output limits and quality metrics from jobs.
2. Recovers missing PSNR/SSIM/sharpness from saved originals and outputs, and saves those
   measurements back to the database. It does not run the upscaler again.
3. Trains OLS, Ridge, Lasso and the mean baseline once at least 10 different source filenames
   have usable measurements. Videos, unfinished jobs and zero-sharpness images are excluded.
4. Publishes `<storage.dir>/qop/models.json` atomically. Changed training data triggers a new
   fit; an unchanged dataset does not. A failed fit keeps the previous model available.

The tab shows completed/usable jobs, distinct images, missing files and training status;
it refreshes automatically. Missing saved media are counted rather than crashing the update.
Automatic training uses `content_type=unknown` because jobs do not store manual labels.

Settings in `backend/config.yml`, also configurable with `QOP__...` environment variables:

```yaml
qop:
  enabled: true
  poll_interval: 30
  min_images: 10
```

With separate API and queue-worker containers, automatic training runs in the API process
and sees the same shared database and data volume. Pandas and scikit-learn are included in
the backend dependencies. Model fitting runs in a background thread and does not block API
startup or prediction requests.

## Optional offline analysis

The CLI uses the same training implementation as the API. Use this workflow for manual
content labels or full CSV reports and plots. Disable automatic training (`QOP__ENABLED=false`)
when deliberately serving a manually exported model; otherwise the database updater owns
the trained model location.

```bash
docker compose up --build                                   # 1. start the app
python analytics/run_dataset.py my_images/ --wait           # 2. 40–60 images × 2K/4K
docker compose exec -T postgres psql -U animeshka -d animeshka --csv -f - \
    < analytics/export_features.sql > analytics/dataset/runs.csv   # 3. export
cp analytics/dataset/content_types.example.csv analytics/dataset/content_types.csv
#   4. put one row per image file name with its content type
pip install -r analytics/requirements.txt
python analytics/qop_regression.py analytics/dataset/runs.csv \
    --labels analytics/dataset/content_types.csv --out analytics/report   # 5. train
```

On Windows PowerShell, `<` does not work: use
`Get-Content analytics/export_features.sql | docker compose exec -T postgres psql -U animeshka -d animeshka --csv -f - > analytics/dataset/runs.csv`.

`analytics/report/` gets `report.md`, `model_comparison.csv`, `coefficients.csv`, `vif.csv`,
`summary.json`, `dataset_with_target.csv` and plots (`actual_vs_predicted.png`,
`residuals.png`, `correlations.png`, `target_distribution.png`).
`python analytics/qop_regression.py --demo` checks the pipeline on synthetic data.

## Models in the app

Open the **Модели** tab (`http://localhost:8080/#models`, or `http://localhost:5173/#models`
with the Vite development server). It provides model comparisons, JSON downloads, and
predictions for an uploaded image in the modes present in the training dataset. The app
includes an explicitly labelled **synthetic demo** so this flow is available before a real
dataset is ready. Demo scores do not validate real upscale quality.

For a manual export with content labels, write to the backend data mount:

```bash
python analytics/qop_regression.py analytics/dataset/runs.csv \
    --labels analytics/dataset/content_types.csv --out backend/data/qop
```

Training now writes `models.json` as well as the report and plots. The backend reads
`<storage.dir>/qop/models.json` on each request, so new exports are available without a
restart. The Compose data mount uses the same location. Do not copy a demo export into
that location: the server checks its source label and rejects it as a trained model.
An export needs at least 10 distinct images; 30–40 or more is recommended. Use stable,
unique filenames to group repeated images correctly.

Predictions use the same input resizing and sharpness calculation as the job worker.
Only categories, modes and output limits represented in the export are offered. QoP
predictions are clipped to 0–1. Image uploads are validated with the app's normal size
limits and are not saved or queued for upscaling. Prediction uses portable linear
coefficients and preprocessing parameters; scikit-learn is used for background training.

Authenticated API endpoints (also documented at `/docs`):

* `GET /api/qop/models?source=trained|demo` — availability, comparisons, coefficients and
  automatic database/training status for trained models
* `GET /api/qop/models/download?source=trained|demo` — portable JSON export
* `POST /api/qop/predict?source=trained|demo` — multipart `file`, `content_type`, `max_size`

The checked-in demo is generated with:

```bash
python analytics/qop_regression.py --demo --out /tmp/qop-demo
cp /tmp/qop-demo/models.json backend/src/features/qop/demo_models.json
```

CI tests the full analytics pipeline and checks that portable predictions match the
scikit-learn pipelines, alongside the API's authorization and upload validation tests.

The 3 indicators (throughput MP/s, quality PSNR/SSIM/QoP, success rate) and per-job QoP are
on the Grafana dashboard **Animeshka — Quality & QoP (PostgreSQL)**. The dashboard normalizes
over the jobs in the selected time range; the trained model uses its training-split bounds.

The database updater computes missing `sharpness_input` from the saved input. Historical
offline CSVs without it still use `sharpness_bicubic` as a proxy.
