"""Image quality metrics saved with every job (table `metrics`) for the analytics dashboard.

An upscaler has no ground truth, so the metrics compare what is available:

* psnr_db / ssim - the result shrunk back to the input size vs the input: how faithful the
  upscale stays to the original (the model must not invent or shift content);
* sharpness_bicubic / sharpness_output - variance of the Laplacian of a plain bicubic resize
  vs the model output at the same size: how much detail the model adds over a resize.

All metrics are computed on the luma (Y) channel, as is usual for super-resolution papers.
"""

import cv2
import numpy as np
from PIL import Image

PSNR_CAP_DB = 100.0  # identical images: PSNR is infinite, JSON and Grafana need a number


def _luma(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"), dtype=np.float64)


def psnr(reference: np.ndarray, test: np.ndarray) -> float:
    mse = float(np.mean((reference - test) ** 2))
    if mse == 0:
        return PSNR_CAP_DB
    return min(10 * np.log10(255.0**2 / mse), PSNR_CAP_DB)


def ssim(reference: np.ndarray, test: np.ndarray) -> float:
    """Mean SSIM with the standard 11x11 Gaussian window (Wang et al., 2004)."""
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2

    def blur(x: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(x, (11, 11), 1.5)

    mu_x, mu_y = blur(reference), blur(test)
    var_x = blur(reference * reference) - mu_x**2
    var_y = blur(test * test) - mu_y**2
    cov = blur(reference * test) - mu_x * mu_y
    ssim_map = ((2 * mu_x * mu_y + c1) * (2 * cov + c2)) / (
        (mu_x**2 + mu_y**2 + c1) * (var_x + var_y + c2)
    )
    return float(ssim_map.mean())


def sharpness(luma: np.ndarray) -> float:
    return float(cv2.Laplacian(luma, cv2.CV_64F).var())


def quality_metrics(source: Image.Image, result: Image.Image) -> dict[str, float]:
    """source = what the model got, result = what it returned."""
    shrunk = result.resize(source.size, Image.Resampling.BICUBIC)
    bicubic = source.resize(result.size, Image.Resampling.BICUBIC)
    source_luma = _luma(source)
    shrunk_luma = _luma(shrunk)
    return {
        "psnr_db": round(psnr(source_luma, shrunk_luma), 4),
        "ssim": round(ssim(source_luma, shrunk_luma), 6),
        "sharpness_bicubic": round(sharpness(_luma(bicubic)), 4),
        "sharpness_output": round(sharpness(_luma(result)), 4),
    }
