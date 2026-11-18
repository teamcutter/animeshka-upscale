"""Validated, portable linear models exported by analytics/qop_regression.py."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Source = Literal["trained", "demo"]
Feature = Literal[
    "input_megapixels",
    "log_input_bytes",
    "log_sharpness_input",
    "aspect_ratio",
    "max_size",
    "mode_4k",
    "content_type",
]


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    feature: Feature
    coefficient: float
    mean: float
    scale: float = Field(gt=0)
    category: str | None = None


class Predictor(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: str
    intercept: float
    terms: list[Term]
    metrics: dict[str, float | None]

    def predict(self, features: dict[str, float | str]) -> float:
        value = self.intercept
        for term in self.terms:
            feature = features[term.feature]
            number = (
                float(feature == term.category)
                if term.feature == "content_type"
                else float(feature)
            )
            value += term.coefficient * (number - term.mean) / term.scale
        return value


class ModelBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal[1]
    source: Source
    created_at: datetime
    target: Literal["qop", "psnr_db"]
    rows: int = Field(ge=10)
    train_images: int = Field(ge=1)
    test_images: int = Field(ge=1)
    best_model: str
    training_max_sizes: list[int] = Field(min_length=1)
    training_modes: list[Literal["2k", "4k"]] = Field(min_length=1)
    content_types: list[str] = Field(min_length=1)
    models: list[Predictor] = Field(min_length=1)
    dataset_fingerprint: str | None = None
