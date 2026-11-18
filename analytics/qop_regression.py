"""Offline entry point for the same QoP training pipeline used by the API."""

import sys
from pathlib import Path

# Allow running this script from the repository root without installing the backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src.features.qop.training import (  # noqa: E402, F401
    Norm,
    demo_data,
    export_models,
    features,
    main,
    models,
    prepare,
    qop,
    run,
)

if __name__ == "__main__":
    main()
