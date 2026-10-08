import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from .rrdb import RRDBNet

logger = logging.getLogger(__name__)


@dataclass
class UpscalerConfig:
    device: str
    tile_size: int
    model_path: str
    scale: int = 2


class RealESRGANUpscaler:
    def __init__(self, config: UpscalerConfig):
        self.config = config
        self.scale = config.scale
        self.device = self._resolve_device(config.device)
        self.tile_size = config.tile_size
        self.tile_pad = 10
        self.model_path = config.model_path
        self.model: RRDBNet | None = None

    @staticmethod
    def _resolve_device(req: str) -> str:
        req = req.lower()
        if req == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        if req == "cuda" and not torch.cuda.is_available():
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.warning("CUDA not available, falling back to mps")
                return "mps"
            logger.warning("CUDA not available, falling back to cpu")
            return "cpu"
        if req == "mps" and not (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        ):
            logger.warning("MPS not available, falling back to cpu")
            return "cpu"
        return req

    @property
    def weights_path(self) -> Path:
        """RealESRGAN_x{scale}plus.pth inside model_path (relative paths resolve from backend/)."""
        mp = Path(self.model_path)
        if not mp.is_absolute():
            mp = (Path(__file__).resolve().parents[3] / mp).resolve()
        return mp / f"RealESRGAN_x{self.scale}plus.pth"

    def is_available(self) -> bool:
        return self.weights_path.is_file()

    def load_model(self) -> None:
        torch.backends.cudnn.benchmark = False
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        model_path = self.weights_path
        if not model_path.exists():
            raise FileNotFoundError(f"Real-ESRGAN weights not found: {model_path}")

        logger.info(f"Loading Real-ESRGAN model from {model_path}")
        self.model = RRDBNet(in_nc=3, out_nc=3, nf=64, nb=23, gc=32, scale=self.scale)

        state_dict = torch.load(model_path, map_location=self.device, weights_only=True)
        if "params_ema" in state_dict:
            state_dict = state_dict["params_ema"]
        elif "params" in state_dict:
            state_dict = state_dict["params"]

        self.model.load_state_dict(state_dict, strict=True)
        self.model.eval()
        self.model = self.model.to(memory_format=torch.channels_last)
        self.model = self.model.to(self.device)

        if self.device == "cuda":
            self.model = self.model.half()

        logger.info(f"Real-ESRGAN loaded (scale={self.scale}x, device={self.device})")

    def unload(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            logger.info("Real-ESRGAN model unloaded")

    def warmup(self) -> None:
        if self.model is None:
            raise RuntimeError("Model not loaded, call load_model() first")
        dummy = Image.new("RGB", (64, 64), color=(128, 128, 128))
        self.enhance(dummy)
        logger.info("Warmup done")

    @torch.inference_mode()
    def enhance(self, image: Image.Image) -> Image.Image:
        if self.model is None:
            raise RuntimeError("Model not loaded")

        img_np = np.array(image)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        img = img_bgr.astype(np.float32) / 255.0
        img = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0)
        img = img.to(self.device, memory_format=torch.channels_last)
        if self.device == "cuda":
            img = img.half()

        _, _, h, w = img.shape

        if h * w > self.tile_size * self.tile_size:
            upscaled = self._tile_process(img)
        else:
            pad_h = h % 2
            pad_w = w % 2
            if pad_h or pad_w:
                img = F.pad(img, (0, pad_w, 0, pad_h), mode="reflect")
            assert self.model is not None
            try:
                upscaled = self.model(img)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    logger.warning("OOM, falling back to tiles")
                    if self.device == "cuda":
                        torch.cuda.empty_cache()
                    upscaled = self._tile_process(img)
                else:
                    raise
            if pad_h or pad_w:
                upscaled = upscaled[:, :, : h * self.scale, : w * self.scale]

        upscaled = upscaled.squeeze(0).permute(1, 2, 0).float().cpu().numpy()
        upscaled = (np.clip(upscaled, 0, 1) * 255).astype(np.uint8)
        upscaled_rgb = cv2.cvtColor(upscaled, cv2.COLOR_BGR2RGB)
        return Image.fromarray(upscaled_rgb)

    def _tile_process(self, img: torch.Tensor) -> torch.Tensor:
        assert self.model is not None
        _, c, h, w = img.shape
        tile = self.tile_size
        tile_pad = self.tile_pad
        scale = self.scale
        out_h, out_w = h * scale, w * scale
        output = torch.zeros((1, c, out_h, out_w), dtype=img.dtype, device=img.device)
        tiles_x = (w + tile - 1) // tile
        tiles_y = (h + tile - 1) // tile
        for y in range(tiles_y):
            for x in range(tiles_x):
                x1 = x * tile
                y1 = y * tile
                x2 = min(x1 + tile, w)
                y2 = min(y1 + tile, h)
                x1p = max(x1 - tile_pad, 0)
                y1p = max(y1 - tile_pad, 0)
                x2p = min(x2 + tile_pad, w)
                y2p = min(y2 + tile_pad, h)
                tile_img = img[:, :, y1p:y2p, x1p:x2p]
                _, _, th, tw = tile_img.shape
                pad_h = th % 2
                pad_w = tw % 2
                if pad_h or pad_w:
                    tile_img = F.pad(tile_img, (0, pad_w, 0, pad_h), mode="reflect")
                tile_out = self.model(tile_img)
                if pad_h or pad_w:
                    tile_out = tile_out[:, :, : th * scale, : tw * scale]
                ox1 = x1 * scale
                oy1 = y1 * scale
                ox2 = x2 * scale
                oy2 = y2 * scale
                px1 = (x1 - x1p) * scale
                py1 = (y1 - y1p) * scale
                px2 = px1 + (x2 - x1) * scale
                py2 = py1 + (y2 - y1) * scale
                output[:, :, oy1:oy2, ox1:ox2] = tile_out[:, :, py1:py2, px1:px2]
        return output
