"""Native macOS GPU service for container workers. No database or queue access."""

import hmac
import logging
import os
import secrets
import threading
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Annotated

import torch
import uvicorn
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from src.container import build_upscalers
from src.core.config import Settings, UpscaleSettings
from src.features.upscale.domain import Mode
from src.features.upscale.ports import Upscaler

logger = logging.getLogger(__name__)


def create_bridge(
    settings: Settings | None = None, *, upscalers: Mapping[Mode, Upscaler] | None = None
) -> FastAPI:
    settings = settings or Settings()
    settings.storage.dir.mkdir(parents=True, exist_ok=True)
    token_path = settings.storage.dir / "mps-bridge.token"
    try:
        descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w") as file:
            file.write(secrets.token_urlsafe(32))
    token = token_path.read_text().strip()
    if not token:
        raise RuntimeError("MPS bridge token is empty")
    models = (
        upscalers
        if upscalers is not None
        else build_upscalers(
            UpscaleSettings(
                backend="realesrgan",
                device="mps",
                model_path=settings.upscale.model_path,
                tile_size=settings.upscale.tile_size,
            )
        )
    )
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS bridge must run natively on a Mac with MPS available")
        try:
            for model in models.values():
                if model.is_available():
                    model.load_model()
                    model.warmup()
            yield
        finally:
            for model in models.values():
                model.unload()

    app = FastAPI(title="Animeshka MPS bridge", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {
            "service": "animeshka-mps",
            "device": "mps",
            "modes": {mode.value: model.is_available() for mode, model in models.items()},
        }

    @app.post("/enhance/{mode}")
    def enhance(
        mode: Mode,
        body: Annotated[bytes, Body(media_type="image/png")],
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        if not hmac.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "Invalid MPS bridge token")
        if len(body) > 32 * 1024 * 1024:
            raise HTTPException(413, "Frame exceeds 32 MB")
        model = models.get(mode)
        if model is None or not model.is_available():
            raise HTTPException(422, "Requested model is unavailable on the MPS bridge")
        try:
            with Image.open(BytesIO(body)) as frame:
                if max(frame.size) > 4096:
                    raise HTTPException(422, "Frame dimensions exceed 4096 pixels")
                image = frame.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(415, "Invalid image frame") from exc
        # A single GPU processes frames serially even when multiple workers connect.
        with lock:
            result = model.enhance(image)
        output = BytesIO()
        result.save(output, format="PNG")
        return Response(output.getvalue(), media_type="image/png")

    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    uvicorn.run(create_bridge(), host="0.0.0.0", port=8766)


if __name__ == "__main__":
    main()
