"""Prefer the native Mac MPS bridge when processing jobs inside a container."""

import json
import logging
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

from src.features.upscale.ports import Upscaler

logger = logging.getLogger(__name__)


class RemoteMPSUpscaler:
    def __init__(self, fallback: Upscaler, url: str, token_path: Path) -> None:
        self.scale = fallback.scale
        self._fallback = fallback
        self._url = url.rstrip("/")
        self._token_path = token_path
        self._remote = False
        self._local_loaded = False

    @property
    def device(self) -> str:
        return "mps" if self._remote else getattr(self._fallback, "device", "cpu")

    def _available(self) -> bool:
        if not self._token_path.is_file():
            return False
        with urlopen(f"{self._url}/health", timeout=1) as response:
            status = json.load(response)
        mode = "2k" if self.scale == 2 else "4k"
        return (
            status.get("service") == "animeshka-mps"
            and status.get("device") == "mps"
            and status.get("modes", {}).get(mode, False)
        )

    def is_available(self) -> bool:
        if self._fallback.is_available():
            return True
        try:
            return self._available()
        except Exception:
            return False

    def load_model(self) -> None:
        try:
            self._remote = self._available()
        except Exception:
            self._remote = False
        if self._remote:
            logger.info(
                "Real-ESRGAN ready (scale=%sx, device=mps, bridge=%s)", self.scale, self._url
            )
        else:
            logger.warning("MPS bridge unavailable; using the local device fallback")
            self._load_local()

    def _load_local(self) -> None:
        if not self._local_loaded:
            self._fallback.load_model()
            self._local_loaded = True

    def warmup(self) -> None:
        if not self._remote:
            self._fallback.warmup()

    def enhance(self, image: Image.Image) -> Image.Image:
        if self._remote:
            try:
                body = BytesIO()
                image.save(body, format="PNG")
                mode = "2k" if self.scale == 2 else "4k"
                request = Request(
                    f"{self._url}/enhance/{mode}",
                    data=body.getvalue(),
                    headers={
                        "Content-Type": "image/png",
                        "Authorization": f"Bearer {self._token_path.read_text().strip()}",
                    },
                )
                with urlopen(request, timeout=120) as response, Image.open(response) as result:
                    if result.size != (image.width * self.scale, image.height * self.scale):
                        raise RuntimeError("MPS bridge returned an unexpected image size")
                    return result.convert("RGB")
            except Exception:
                logger.exception(
                    "MPS bridge request failed; switching this worker to local fallback"
                )
                self._remote = False
        self._load_local()
        return self._fallback.enhance(image)

    def unload(self) -> None:
        if self._local_loaded:
            self._fallback.unload()
            self._local_loaded = False
        self._remote = False
