import pytest
import torch
from PIL import Image

from src.infrastructure.upscale import RRDBNet
from src.infrastructure.upscale.upscaler import RealESRGANUpscaler, UpscalerConfig


def test_rrdb_forward():
    net = RRDBNet()
    x = torch.randn(1, 3, 8, 8)
    y = net(x)
    assert y.shape == (1, 3, 16, 16)


def test_upscaler_enhance_no_weights(tmp_path):
    cfg = UpscalerConfig(device="cpu", tile_size=64, model_path=str(tmp_path), scale=2)
    up = RealESRGANUpscaler(cfg)
    with pytest.raises(FileNotFoundError):
        up.load_model()


def test_enhance_with_mock_model():
    cfg = UpscalerConfig(device="cpu", tile_size=32, model_path="/tmp", scale=2)
    up = RealESRGANUpscaler(cfg)
    up.model = RRDBNet()
    up.model.eval()
    img = Image.new("RGB", (16, 16), color=(100, 150, 200))
    out = up.enhance(img)
    assert out.size == (32, 32)


def test_tile_process():
    cfg = UpscalerConfig(device="cpu", tile_size=16, model_path="/tmp", scale=2)
    up = RealESRGANUpscaler(cfg)
    up.model = RRDBNet()
    up.model.eval()
    img_t = torch.randn(1, 3, 32, 32)
    out = up._tile_process(img_t)
    assert out.shape == (1, 3, 64, 64)
