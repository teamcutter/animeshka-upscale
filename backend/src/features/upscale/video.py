"""Decode one frame at a time and encode an MP4 with the original audio."""

import math
import shutil
import subprocess
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryFile

import cv2
from PIL import Image

from src.shared.errors import InvalidMediaError


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    frames: int = 0

    @property
    def duration_seconds(self) -> float:
        return self.frames / self.fps


def probe_video(path: Path) -> VideoInfo:
    capture = cv2.VideoCapture(str(path))
    try:
        ok, frame = capture.read()
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not ok or frame is None or not math.isfinite(fps) or fps <= 0:
            raise InvalidMediaError("Video is unreadable or has an invalid frame rate")
        height, width = frame.shape[:2]
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(frames) or frames < 1:
            raise InvalidMediaError("Video has no known duration")
        return VideoInfo(width, height, fps, int(frames))
    finally:
        capture.release()


def video_frame_range(info: VideoInfo, start: float, end: float | None) -> tuple[int, int]:
    if not math.isfinite(start) or start < 0 or start >= info.duration_seconds:
        raise InvalidMediaError("Video start must be within the source duration")
    if end is not None and (
        not math.isfinite(end) or end <= start or end > info.duration_seconds + 0.001
    ):
        raise InvalidMediaError("Video end must be after the start and within the source duration")
    first = math.ceil(start * info.fps - 1e-6)
    last = min(math.ceil(end * info.fps - 1e-6), info.frames) if end is not None else info.frames
    if last <= first:
        raise InvalidMediaError("Selected interval contains no video frames")
    return first, last


def create_video_preview(source: Path, output: Path, start: float, duration: float) -> None:
    if shutil.which("ffmpeg") is None:
        raise InvalidMediaError("Video previews require FFmpeg on the API server")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(source),
                "-t",
                str(duration),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                "scale=w='min(640,trunc(iw/2)*2)':h=-2",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InvalidMediaError("Could not generate a preview for this video") from exc


def upscale_video(
    source: Path,
    output: Path,
    enhance: Callable[[Image.Image], Image.Image],
    *,
    start_seconds: float = 0,
    end_seconds: float | None = None,
) -> VideoInfo:
    """Stream RGB frames to H.264; AAC audio is optional for silent uploads.

    stderr goes to a file so an encoder error cannot fill a pipe and block inference.
    All decoder/encoder resources and any partial output are cleaned up on failure.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("Video upscaling requires FFmpeg; install it on the worker")
    info = probe_video(source)
    first_frame, last_frame = video_frame_range(info, start_seconds, end_seconds)
    capture = cv2.VideoCapture(str(source))
    encoder = None
    frames = 0
    size = None
    try:
        if first_frame and not capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame):
            raise InvalidMediaError("Could not seek to the selected video start")
        with TemporaryFile() as errors:
            while frames < last_frame - first_frame:
                ok, frame = capture.read()
                if not ok:
                    break
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = enhance(image).convert("RGB")
                if encoder is None:
                    size = result.size
                    encoder = subprocess.Popen(
                        [
                            "ffmpeg",
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-y",
                            "-f",
                            "rawvideo",
                            "-pix_fmt",
                            "rgb24",
                            "-s",
                            f"{result.width}x{result.height}",
                            "-r",
                            str(info.fps),
                            "-i",
                            "pipe:0",
                            "-ss",
                            str(first_frame / info.fps),
                            "-t",
                            str((last_frame - first_frame) / info.fps),
                            "-i",
                            str(source),
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0?",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "veryfast",
                            "-crf",
                            "18",
                            "-vf",
                            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                            "-pix_fmt",
                            "yuv420p",
                            "-c:a",
                            "aac",
                            "-movflags",
                            "+faststart",
                            str(output),
                        ],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=errors,
                    )
                elif result.size != size:
                    raise InvalidMediaError("Video frame dimensions changed during processing")
                assert encoder.stdin is not None
                try:
                    encoder.stdin.write(result.tobytes())
                except BrokenPipeError as exc:
                    errors.seek(0)
                    detail = errors.read().decode(errors="replace").strip()
                    raise RuntimeError(f"Video encoding failed: {detail[-2000:]}") from exc
                frames += 1

            if encoder is None or size is None:
                raise InvalidMediaError("Video contains no readable frames")
            assert encoder.stdin is not None
            encoder.stdin.close()
            if encoder.wait(timeout=120) != 0:
                errors.seek(0)
                detail = errors.read().decode(errors="replace").strip()
                raise RuntimeError(f"Video encoding failed: {detail[-2000:]}")
        # yuv420p needs even dimensions; FFmpeg pads the right/bottom by at most one pixel.
        width, height = size
        return VideoInfo(width + width % 2, height + height % 2, info.fps, frames)
    except BaseException:
        if encoder is not None:
            if encoder.poll() is None:
                encoder.kill()
            encoder.wait()
            if encoder.stdin is not None:
                with suppress(BrokenPipeError):
                    encoder.stdin.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        capture.release()
