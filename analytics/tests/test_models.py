import json

import numpy as np
import pandas as pd
import pytest

from analytics import qop_regression as qop


def portable_prediction(model, row):
    value = model["intercept"]
    for term in model["terms"]:
        x = (
            float(row["content_type"] == term["category"])
            if term["feature"] == "content_type"
            else row[term["feature"]]
        )
        value += term["coefficient"] * (x - term["mean"]) / term["scale"]
    return value


def test_exported_predictors_match_sklearn(tmp_path):
    df = qop.demo_data(40)
    df["max_size"] = np.where(np.arange(40) % 2, 1920, 2048)
    df = qop.prepare(df)
    cols = qop.features(df)
    target = qop.qop(df, qop.Norm.fit(df))
    models = qop.models(cols, 3, df["filename"].to_numpy())
    for model in models.values():
        model.fit(df[cols], target)
    table = pd.DataFrame([{"model": name, "R2_test": 0.5} for name in models])
    summary = {
        "target": "qop",
        "rows": 40,
        "train_images": 32,
        "test_images": 8,
        "best_model": "OLS",
    }
    qop.export_models(models, table, summary, df, tmp_path, demo=True)
    artifact = json.loads((tmp_path / "models.json").read_text())
    for exported in artifact["models"]:
        expected = models[exported["name"]].predict(df[cols])
        actual = [portable_prediction(exported, row) for _, row in df.iterrows()]
        np.testing.assert_allclose(actual, expected, atol=1e-12)


def test_full_run_keeps_paired_images_together_and_fits_fold_bounds(
    tmp_path, monkeypatch
):
    images = qop.demo_data(20)
    df = pd.concat(
        [images.assign(mode="2k"), images.assign(mode="4k")], ignore_index=True
    )
    fitted_groups = []
    original_fit = qop.Norm.fit

    def track_fit(rows):
        fitted_groups.append(set(rows["filename"]))
        return original_fit(rows)

    monkeypatch.setattr(qop.Norm, "fit", track_fit)
    summary = qop.run(df, "qop", tmp_path, 3, demo=True)
    rows = pd.read_csv(tmp_path / "dataset_with_target.csv")
    assert rows.groupby("filename")["split"].nunique().max() == 1
    assert summary["train_images"] == 16
    assert summary["test_images"] == 4
    assert len(fitted_groups) == 1 + 4 * 3
    assert all(groups < fitted_groups[0] for groups in fitted_groups[1:])
    artifact = json.loads((tmp_path / "models.json").read_text())
    assert artifact["source"] == "demo"
    assert len(artifact["models"]) == 4
    assert (tmp_path / "actual_vs_predicted.png").is_file()


def test_too_few_distinct_images_cannot_be_hidden_by_repeated_runs(tmp_path):
    df = pd.concat([qop.demo_data(4)] * 5, ignore_index=True)
    with pytest.raises(SystemExit, match="10 distinct"):
        qop.run(df, "qop", tmp_path, 3)
