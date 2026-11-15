"""QoP (Quality of Processing) model: multiple linear regression, Sprint 6 (S6-1, S6-2).

Predicts the quality of an upscale BEFORE it runs, from what is known about the input file
and the chosen settings. Methodology: research memo of Sprint 5.

    target  QoP = 0.4*norm(PSNR) + 0.4*SSIM + 0.2*norm(sharpness_output / sharpness_bicubic)
            norm() = min-max scaling to 0..1 on the training split; backup target: psnr_db
    features  input_megapixels, mode (2K=0 / 4K=1), log(input_bytes), log(sharpness_input),
              aspect ratio, content_type (one-hot, optional labels file)
    models    naive mean baseline, OLS, Ridge, Lasso; 80/20 split + k-fold CV
    report    R2, adjusted R2, MAE, RMSE, VIF, coefficients, residual plots

Usage (from the repo root):
    python analytics/qop_regression.py analytics/dataset/runs.csv \
        --labels analytics/dataset/content_types.csv --out analytics/report
    python analytics/qop_regression.py --demo --out analytics/report_demo   # synthetic data

Needs: pandas, numpy, scikit-learn, matplotlib (pip install -r analytics/requirements.txt).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LassoCV, LinearRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

QOP_WEIGHTS = {"psnr": 0.4, "ssim": 0.4, "sharpness_gain": 0.2}  # fixed before training
NUMERIC = ["input_megapixels", "log_input_bytes", "log_sharpness_input", "aspect_ratio"]
BINARY = ["mode_4k"]
CATEGORICAL = ["content_type"]
SEED = 42


# ---------------------------------------------------------------- data


def load(csv: Path, labels: Path | None) -> pd.DataFrame:
    df = pd.read_csv(csv)
    if labels is not None:
        tags = pd.read_csv(labels)[["filename", "content_type"]]
        df = df.drop(columns=["content_type"], errors="ignore").merge(
            tags, on="filename", how="left"
        )
    if "content_type" not in df:
        df["content_type"] = "unknown"
    df["content_type"] = df["content_type"].fillna("unknown").astype(str).str.strip().str.lower()
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Clean rows and derive model features (input side only: no output metrics -> no leakage)."""
    required = [
        "mode",
        "width",
        "height",
        "input_bytes",
        "psnr_db",
        "ssim",
        "sharpness_bicubic",
        "sharpness_output",
    ]
    missing = [c for c in required if c not in df]
    if missing:
        raise SystemExit(f"CSV is missing columns: {missing}. Export it with export_features.sql")
    df = df.dropna(subset=required).copy()
    df = df[(df["sharpness_bicubic"] > 0) & (df["input_bytes"] > 0)]
    if "input_megapixels" not in df or df["input_megapixels"].isna().any():
        df["input_megapixels"] = df["width"] * df["height"] / 1e6
    df["mode_4k"] = (df["mode"].astype(str).str.lower() == "4k").astype(int)
    df["log_input_bytes"] = np.log(df["input_bytes"].astype(float))
    if "sharpness_input" not in df or df["sharpness_input"].isna().all():
        # Jobs made before sharpness_input existed: the bicubic resize is a close proxy.
        df["sharpness_input"] = df["sharpness_bicubic"]
    df["sharpness_input"] = df["sharpness_input"].fillna(df["sharpness_bicubic"])
    df["log_sharpness_input"] = np.log1p(df["sharpness_input"].astype(float))
    df["aspect_ratio"] = df["width"] / df["height"]
    df["sharpness_gain"] = df["sharpness_output"] / df["sharpness_bicubic"]
    return df.reset_index(drop=True)


@dataclass
class Norm:
    """min-max bounds fitted on the training split only, then reused for the test split."""

    lo: dict[str, float]
    hi: dict[str, float]

    @classmethod
    def fit(cls, df: pd.DataFrame) -> Norm:
        cols = ["psnr_db", "sharpness_gain"]
        return cls({c: float(df[c].min()) for c in cols}, {c: float(df[c].max()) for c in cols})

    def scale(self, s: pd.Series, col: str) -> pd.Series:
        span = self.hi[col] - self.lo[col]
        return ((s - self.lo[col]) / span).clip(0, 1) if span > 0 else s * 0 + 0.5


def qop(df: pd.DataFrame, norm: Norm) -> pd.Series:
    return (
        QOP_WEIGHTS["psnr"] * norm.scale(df["psnr_db"], "psnr_db")
        + QOP_WEIGHTS["ssim"] * df["ssim"].clip(0, 1)
        + QOP_WEIGHTS["sharpness_gain"] * norm.scale(df["sharpness_gain"], "sharpness_gain")
    )


# ---------------------------------------------------------------- models


def features(df: pd.DataFrame) -> list[str]:
    cats = CATEGORICAL if df["content_type"].nunique() > 1 else []
    bins = [c for c in BINARY if df[c].nunique() > 1]
    nums = [c for c in NUMERIC if df[c].nunique() > 1]
    return nums + bins + cats


def preprocessor(cols: list[str]) -> ColumnTransformer:
    parts = [("num", StandardScaler(), [c for c in cols if c in NUMERIC])]
    if any(c in BINARY for c in cols):
        parts.append(("bin", "passthrough", [c for c in cols if c in BINARY]))
    if "content_type" in cols:
        parts.append(("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), CATEGORICAL))
    return ColumnTransformer(parts, verbose_feature_names_out=False)


def models(cols: list[str], folds: int) -> dict[str, Pipeline]:
    alphas = np.logspace(-3, 3, 25)
    inner = max(2, min(5, folds))
    return {
        "Naive mean": Pipeline([("prep", preprocessor(cols)), ("m", DummyRegressor())]),
        "OLS": Pipeline([("prep", preprocessor(cols)), ("m", LinearRegression())]),
        "Ridge": Pipeline([("prep", preprocessor(cols)), ("m", RidgeCV(alphas=alphas))]),
        "Lasso": Pipeline(
            [
                ("prep", preprocessor(cols)),
                ("m", LassoCV(alphas=alphas / 100, cv=inner, max_iter=50_000, random_state=SEED)),
            ]
        ),
    }


def adjusted_r2(r2: float, n: int, p: int) -> float:
    return float("nan") if n - p - 1 <= 0 else 1 - (1 - r2) * (n - 1) / (n - p - 1)


def vif(x: np.ndarray, names: list[str]) -> pd.DataFrame:
    rows = []
    for j, name in enumerate(names):
        others = np.delete(x, j, axis=1)
        if others.shape[1] == 0:
            rows.append((name, 1.0))
            continue
        r2 = LinearRegression().fit(others, x[:, j]).score(others, x[:, j])
        rows.append((name, float("inf") if r2 >= 1 else 1 / (1 - r2)))
    return pd.DataFrame(rows, columns=["feature", "VIF"])


# ---------------------------------------------------------------- run


def run(df: pd.DataFrame, target: str, out: Path, folds: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    df = prepare(df)
    n = len(df)
    if n < 10:
        raise SystemExit(f"Only {n} usable jobs: process at least 30-40 images first.")
    cols = features(df)

    train, test = train_test_split(df, test_size=0.2, random_state=SEED)
    norm = Norm.fit(train)
    if target == "qop":
        y_train, y_test, y_all = qop(train, norm), qop(test, norm), qop(df, norm)
    else:
        y_train, y_test, y_all = train[target], test[target], df[target]

    folds = max(2, min(folds, len(train) // 3))
    kf = KFold(n_splits=folds, shuffle=True, random_state=SEED)
    results, fitted = [], {}
    for name, model in models(cols, folds).items():
        cv = cross_validate(
            model,
            train[cols],
            y_train,
            cv=kf,
            scoring=("r2", "neg_mean_absolute_error", "neg_root_mean_squared_error"),
        )
        model.fit(train[cols], y_train)
        pred = model.predict(test[cols])
        p = 0 if name == "Naive mean" else len(model.named_steps["prep"].get_feature_names_out())
        r2_train = r2_score(y_train, model.predict(train[cols]))
        results.append(
            {
                "model": name,
                "R2_train": r2_train,
                "adj_R2_train": adjusted_r2(r2_train, len(train), p),
                "R2_test": r2_score(y_test, pred),
                "MAE_test": mean_absolute_error(y_test, pred),
                "RMSE_test": float(np.sqrt(mean_squared_error(y_test, pred))),
                "R2_cv_mean": cv["test_r2"].mean(),
                "R2_cv_std": cv["test_r2"].std(),
                "RMSE_cv_mean": -cv["test_neg_root_mean_squared_error"].mean(),
            }
        )
        fitted[name] = model
    table = pd.DataFrame(results)
    table.to_csv(out / "model_comparison.csv", index=False)

    # Coefficients of OLS on standardized features (comparable magnitudes).
    ols = fitted["OLS"]
    names = list(ols.named_steps["prep"].get_feature_names_out())
    coefs = pd.DataFrame(
        {
            "feature": ["intercept", *names],
            "coefficient": [ols.named_steps["m"].intercept_, *ols.named_steps["m"].coef_],
        }
    )
    for name in ("Ridge", "Lasso"):
        m = fitted[name].named_steps["m"]
        coefs[name] = [m.intercept_, *m.coef_]
    coefs.to_csv(out / "coefficients.csv", index=False)

    x_train = ols.named_steps["prep"].transform(train[cols])
    x_train = x_train.toarray() if hasattr(x_train, "toarray") else np.asarray(x_train)
    vifs = vif(x_train, names)
    vifs.to_csv(out / "vif.csv", index=False)

    best = table[table["model"] != "Naive mean"].sort_values("RMSE_cv_mean").iloc[0]["model"]
    _plots(df, y_all, test, y_test, fitted["OLS"].predict(test[cols]), cols, out, target)

    data = df.assign(target=y_all)
    data.to_csv(out / "dataset_with_target.csv", index=False)
    summary = {
        "target": target,
        "rows": n,
        "train": len(train),
        "test": len(test),
        "folds": folds,
        "features": cols,
        "best_model": best,
        "norm_bounds": {"lo": norm.lo, "hi": norm.hi},
        "qop_weights": QOP_WEIGHTS,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    _report(summary, table, coefs, vifs, out)
    return summary


def _plots(df, y_all, test, y_test, pred, cols, out: Path, target: str) -> None:
    label = "QoP" if target == "qop" else target
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(y_test, pred, alpha=0.7)
    lo, hi = float(min(y_test.min(), pred.min())), float(max(y_test.max(), pred.max()))
    ax.plot([lo, hi], [lo, hi], "--", color="gray")
    ax.set(
        xlabel=f"{label} actual",
        ylabel=f"{label} predicted (OLS)",
        title="Test: actual vs predicted",
    )
    fig.tight_layout()
    fig.savefig(out / "actual_vs_predicted.png", dpi=150)
    plt.close(fig)

    resid = y_test - pred
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].scatter(pred, resid, alpha=0.7)
    axes[0].axhline(0, color="gray", ls="--")
    axes[0].set(xlabel="predicted", ylabel="residual", title="Residuals vs predicted")
    axes[1].hist(resid, bins=15)
    axes[1].set(xlabel="residual", title="Residual distribution")
    fig.tight_layout()
    fig.savefig(out / "residuals.png", dpi=150)
    plt.close(fig)

    numeric = [c for c in [*NUMERIC, *BINARY] if c in cols]
    corr = df[numeric].assign(**{label: y_all}).corr()
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)), corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im)
    ax.set_title("Correlation matrix (EDA)")
    fig.tight_layout()
    fig.savefig(out / "correlations.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    for mode, part in df.assign(y=y_all).groupby("mode"):
        ax.hist(part["y"], bins=15, alpha=0.6, label=str(mode))
    ax.set(xlabel=label, ylabel="jobs", title=f"{label} distribution by mode")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "target_distribution.png", dpi=150)
    plt.close(fig)


def _report(summary, table, coefs, vifs, out: Path) -> None:
    fmt = lambda d: d.to_markdown(index=False, floatfmt=".4f")  # noqa: E731
    text = f"""# QoP regression report

Target: **{summary["target"]}**, jobs: {summary["rows"]} (train {summary["train"]},
test {summary["test"]}), {summary["folds"]}-fold CV on train.
Features: {", ".join(summary["features"])}.
Best model by CV RMSE: **{summary["best_model"]}**.

## Model comparison

{fmt(table)}

A model is useful when it beats **Naive mean** clearly and its CV R2 is stable (small std).

## Coefficients (standardized features)

{fmt(coefs)}

## Multicollinearity (VIF, train)

{fmt(vifs)}

VIF above 5-10 means the feature duplicates others: drop one of them.

Plots: actual_vs_predicted.png, residuals.png, correlations.png, target_distribution.png.
"""
    (out / "report.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- demo data


def demo_data(n: int = 120) -> pd.DataFrame:
    """Synthetic runs with the export schema, only to check that the pipeline works."""
    rng = np.random.default_rng(SEED)
    kinds = rng.choice(["anime", "portrait", "landscape", "text", "noise"], n)
    w = rng.integers(320, 1600, n)
    h = (w * rng.uniform(0.55, 1.4, n)).astype(int)
    mode = rng.choice(["2k", "4k"], n)
    mp = w * h / 1e6
    sharp_in = rng.lognormal(5, 0.6, n) * np.where(kinds == "noise", 3, 1)
    base = {"anime": 38, "portrait": 34, "landscape": 32, "text": 36, "noise": 27}
    psnr = (
        np.array([base[k] for k in kinds]) - 2 * (mode == "4k") - 1.5 * mp + rng.normal(0, 1.2, n)
    )
    return pd.DataFrame(
        {
            "filename": [f"img_{i:03d}.png" for i in range(n)],
            "mode": mode,
            "width": w,
            "height": h,
            "input_bytes": (mp * 1e6 * rng.uniform(0.3, 2.5, n)).astype(int),
            "input_megapixels": mp,
            "sharpness_input": sharp_in,
            "psnr_db": psnr,
            "ssim": np.clip(0.55 + psnr / 100 + rng.normal(0, 0.02, n), 0, 1),
            "sharpness_bicubic": sharp_in * 0.4,
            "sharpness_output": sharp_in * 0.4 * rng.uniform(1.1, 2.2, n),
            "content_type": kinds,
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", nargs="?", type=Path, help="runs.csv from export_features.sql")
    ap.add_argument("--labels", type=Path, help="CSV filename,content_type")
    ap.add_argument("--target", choices=["qop", "psnr_db"], default="qop")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--out", type=Path, default=Path("analytics/report"))
    ap.add_argument("--demo", action="store_true", help="run on synthetic data")
    args = ap.parse_args()
    if args.demo:
        df = demo_data()
    elif args.csv:
        df = load(args.csv, args.labels)
    else:
        ap.error("pass a CSV or --demo")
    summary = run(df, args.target, args.out, args.folds)
    print((args.out / "report.md").read_text(encoding="utf-8"))
    print(f"Saved to {args.out}/ (best model: {summary['best_model']})")


if __name__ == "__main__":
    main()
