from PIL import Image


class StubUpscaler:
    """Lanczos stand-in for RealESRGANUpscaler: no weights, no torch.

    Used in tests/CI and on machines without the model weights (upscale.backend: stub).
    """

    def __init__(self, scale: int) -> None:
        self.scale = scale

    def is_available(self) -> bool:
        return True

    def load_model(self) -> None:
        pass

    def warmup(self) -> None:
        pass

    def enhance(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        return image.resize((width * self.scale, height * self.scale), Image.Resampling.LANCZOS)

    def unload(self) -> None:
        pass
