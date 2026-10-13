import numpy as np
from PIL import Image, ImageFilter

from src.features.upscale.quality import PSNR_CAP_DB, quality_metrics


def checkerboard(size: int = 64, cell: int = 4) -> Image.Image:
    pattern = (np.indices((size, size)) // cell).sum(axis=0) % 2
    return Image.fromarray((pattern * 255).astype(np.uint8)).convert("RGB")


def test_identical_images_score_perfectly() -> None:
    image = checkerboard()
    metrics = quality_metrics(image, image)
    assert metrics["psnr_db"] == PSNR_CAP_DB
    assert metrics["ssim"] == 1.0


def test_distortion_lowers_psnr_and_ssim() -> None:
    image = checkerboard()
    blurred = image.filter(ImageFilter.GaussianBlur(2))
    metrics = quality_metrics(image, blurred)
    assert metrics["psnr_db"] < 30
    assert metrics["ssim"] < 0.9


def test_sharpness_compares_with_plain_resize() -> None:
    source = checkerboard(32, 4)
    # Nearest keeps hard edges: sharper than the bicubic resize the metric compares with.
    sharp = source.resize((64, 64), Image.Resampling.NEAREST)
    metrics = quality_metrics(source, sharp)
    assert metrics["sharpness_output"] > metrics["sharpness_bicubic"]
