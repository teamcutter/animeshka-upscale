"""Device selection shared by the API worker and offline CLI."""

import logging

import torch

logger = logging.getLogger(__name__)


def resolve_device(requested: str) -> str:
    requested = requested.lower()
    if requested not in {"auto", "cpu", "mps", "cuda"}:
        raise ValueError(f"Unknown upscale device: {requested}")
    if requested == "cpu":
        return "cpu"
    mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    if requested == "mps":
        if mps_available:
            return "mps"
        logger.warning("MPS not available, falling back to cpu")
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if mps_available:
        if requested == "cuda":
            logger.warning("CUDA not available, falling back to mps")
        return "mps"
    if requested == "cuda":
        logger.warning("CUDA not available, falling back to cpu")
    return "cpu"
