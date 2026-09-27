from PIL import Image


class StubUpscaler:
    """Lanczos stand-in for RealESRGANUpscaler until the RRDB module (#1) lands.

    Mirrors its resizing contract: input is downsized so the output fits max_size.
    """

    def __init__(self, scale: int) -> None:
        self.scale = scale

    def load_model(self) -> None:
        pass

    def warmup(self, max_size: int = 1920) -> None:
        pass

    def enhance(self, image: Image.Image, max_size: int = 1920) -> Image.Image:
        limit = max_size // self.scale
        if max(image.size) > limit:
            image = image.copy()
            image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        width, height = image.size
        return image.resize((width * self.scale, height * self.scale), Image.Resampling.LANCZOS)

    def unload(self) -> None:
        pass
