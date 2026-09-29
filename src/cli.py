import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import torch
from PIL import Image

from src.core.config import get_settings
from src.infrastructure.upscale import RealESRGANUpscaler, UpscalerConfig

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def build_parser() -> argparse.ArgumentParser:
    s = get_settings()
    p = argparse.ArgumentParser(
        prog="animeshka-upscale",
        description="Real-ESRGAN anime upscaler (image/video) native 2x/4x",
    )
    p.add_argument("input", type=Path, help="input image or video path")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output path (default: <input>_x<scale>.<ext>)",
    )
    p.add_argument(
        "--scale",
        type=int,
        default=s.upscale.scale,
        choices=[2, 4],
        help="upscale factor 2=2K 4=4K",
    )
    p.add_argument("--tile-size", type=int, default=s.upscale.tile_size, help="tile size")
    p.add_argument("--device", type=str, default=s.upscale.device, help="auto|cuda|mps|cpu")
    p.add_argument(
        "--model-path", type=Path, default=s.upscale.resolved_model_path, help="weights dir"
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def resolve_device(req: str) -> str:
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
    if req == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
        logger.warning("MPS not available, falling back to cpu")
        return "cpu"
    return req


def make_upscaler(args: argparse.Namespace) -> RealESRGANUpscaler:
    mp = args.model_path
    if not mp.is_absolute() and not mp.exists():
        from src.core.config import CONFIG_PATH

        mp = (CONFIG_PATH.parent / mp).resolve()
    cfg = UpscalerConfig(
        device=resolve_device(args.device),
        tile_size=args.tile_size,
        model_path=str(mp),
        scale=args.scale,
    )
    up = RealESRGANUpscaler(cfg)
    up.load_model()
    up.warmup()
    return up


def upscale_image(up: RealESRGANUpscaler, inp: Path, out: Path) -> None:
    img = Image.open(inp).convert("RGB")
    logger.info(f"upscaling {inp} {img.size} -> x{up.scale} native")
    res = up.enhance(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    res.save(out)
    logger.info(f"saved {out} {res.size}")


def upscale_video(up: RealESRGANUpscaler, inp: Path, out: Path) -> None:
    cap = cv2.VideoCapture(str(inp))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video {inp}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"video {inp} {w}x{h} @ {fps:.2f}fps -> x{up.scale}")

    with tempfile.TemporaryDirectory() as td:
        tmp_out = Path(td) / "upscaled.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        ow, oh = w * up.scale, h * up.scale
        writer = cv2.VideoWriter(str(tmp_out), fourcc, fps, (ow, oh))
        if not writer.isOpened():
            raise RuntimeError("cannot open VideoWriter")

        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            upscaled = up.enhance(pil)
            out_frame = cv2.cvtColor(__import__("numpy").array(upscaled), cv2.COLOR_RGB2BGR)
            if (out_frame.shape[1], out_frame.shape[0]) != (ow, oh):
                ow, oh = out_frame.shape[1], out_frame.shape[0]
                writer.release()
                writer = cv2.VideoWriter(str(tmp_out), fourcc, fps, (ow, oh))
                if idx > 0:
                    raise RuntimeError("dynamic output size not supported for video")
            writer.write(out_frame)
            idx += 1
            if idx % 10 == 0:
                logger.info(f"frame {idx}")

        cap.release()
        writer.release()

        has_audio = (
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "csv=p=0",
                    str(inp),
                ],
                capture_output=True,
                text=True,
            ).stdout.strip()
            != ""
        )

        if has_audio:
            logger.info("muxing audio via ffmpeg")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(tmp_out),
                    "-i",
                    str(inp),
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-shortest",
                    str(out),
                ],
                check=True,
            )
        else:
            tmp_out.rename(out)

    logger.info(f"saved video {out}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s"
    )

    if not args.input.exists():
        parser.error(f"input not found: {args.input}")

    out = args.output
    if out is None:
        out = args.input.with_name(f"{args.input.stem}_x{args.scale}{args.input.suffix}")

    up = make_upscaler(args)
    try:
        if args.input.suffix.lower() in VIDEO_EXTS:
            upscale_video(up, args.input, out)
        else:
            upscale_image(up, args.input, out)
    finally:
        up.unload()
    return 0


if __name__ == "__main__":
    sys.exit(main())
