import logging
import math
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from src.core.config import ImageSettings
from src.features.qop.models import ModelBundle, Source
from src.features.upscale.quality import sharpness
from src.features.upscale.service import IMAGE_FORMATS, fit_to_output
from src.shared.errors import AppError, InvalidMediaError, UnsupportedMediaTypeError

logger = logging.getLogger(__name__)


class ModelsUnavailableError(AppError):
    status_code = 503


def bundle_path(storage: Path, source: Source) -> Path:
    if source == "demo":
        return Path(__file__).with_name("demo_models.json")
    return storage / "qop" / "models.json"


def load_models(storage: Path, source: Source) -> ModelBundle | None:
    path = bundle_path(storage, source)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        bundle = ModelBundle.model_validate_json(raw)
        if bundle.source != source:
            raise ValueError("Bundle source does not match requested source")
        return bundle
    except (ValidationError, ValueError) as exc:
        logger.error("Invalid QoP model bundle: %s", path)
        raise ModelsUnavailableError(
            "The model export is invalid. Export the models again."
        ) from exc


def predict(
    storage: Path,
    source: Source,
    data: bytes,
    content_type: str,
    max_size: int,
    limits: ImageSettings,
) -> dict:
    bundle = load_models(storage, source)
    if bundle is None:
        raise ModelsUnavailableError("No trained QoP models are available yet.")
    if max_size not in bundle.training_max_sizes:
        raise InvalidMediaError("Choose an output limit used to train these models.")
    content_type = content_type.strip().lower()
    if content_type not in bundle.content_types:
        raise InvalidMediaError("Choose a content type used to train these models.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in IMAGE_FORMATS:
                raise UnsupportedMediaTypeError("File is not a supported image")
            width, height = image.size
            if width > limits.max_width or height > limits.max_height:
                raise InvalidMediaError(f"Image exceeds {limits.max_width}x{limits.max_height}")
            rgb = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise UnsupportedMediaTypeError("File is not a supported image") from exc

    predictions = []
    for mode in bundle.training_modes:
        # Match the resized input and rounded sharpness stored by the job worker.
        model_input = fit_to_output(rgb, max_size, 4 if mode == "4k" else 2)
        input_sharpness = round(
            sharpness(np.asarray(model_input.convert("L"), dtype=np.float64)), 4
        )
        features: dict[str, float | str] = {
            "input_megapixels": round(width * height / 1e6, 4),
            "log_input_bytes": math.log(len(data)),
            "log_sharpness_input": math.log1p(input_sharpness),
            "aspect_ratio": width / height,
            "max_size": max_size,
            "mode_4k": float(mode == "4k"),
            "content_type": content_type,
        }
        for model in bundle.models:
            raw = model.predict(features)
            score = min(1.0, max(0.0, raw)) if bundle.target == "qop" else raw
            predictions.append({"mode": mode, "model": model.name, "value": round(score, 6)})
    return {
        "source": bundle.source,
        "target": bundle.target,
        "width": width,
        "height": height,
        "predictions": predictions,
    }
