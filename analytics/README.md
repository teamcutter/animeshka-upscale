# Analytics: dataset, indicators and the QoP regression (Sprints 5–6)

Methodology: research memo of Sprint 5. The model predicts the quality of an upscale **before**
it runs, from the input file and the settings.

```
QoP = 0.4·norm(PSNR) + 0.4·SSIM + 0.2·norm(sharpness_output / sharpness_bicubic)
```

`norm()` is min-max scaling to 0..1 fitted on the training split. Backup target: `psnr_db`.

| File | What it does |
|---|---|
| `run_dataset.py` | uploads a folder of images through the running app in 2K and 4K |
| `export_features.sql` | one row per finished image job: input features + quality metrics |
| `dataset/content_types.example.csv` | template for manual `content_type` labels (anime, portrait, landscape, text, noise) |
| `qop_regression.py` | EDA, QoP target, OLS vs Ridge vs Lasso vs naive mean, R2 / adj. R2 / MAE / RMSE, k-fold CV, VIF, plots |

Features (input side only, no output metrics → no data leakage): `input_megapixels`,
`mode_4k`, `log(input_bytes)`, `log(sharpness_input)`, aspect ratio, `content_type` (one-hot).

## Steps

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

The 3 indicators (throughput MP/s, quality PSNR/SSIM/QoP, success rate) and per-job QoP are
on the Grafana dashboard **Animeshka — Quality & QoP (PostgreSQL)**. The dashboard normalizes
over the jobs in the selected time range; the trained model uses its training-split bounds.

Jobs made before `sharpness_input` was added fall back to `sharpness_bicubic` as a proxy.
