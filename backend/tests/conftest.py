import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

from src.app import create_app
from src.core.config import (
    DatabaseSettings,
    ImageSettings,
    Settings,
    StorageSettings,
    UpscaleSettings,
    VideoSettings,
    WorkerSettings,
)
from src.infrastructure.db.engine import create_db_engine
from src.infrastructure.db.models import Base

# Set to a PostgreSQL URL to run the suite against a real server (CI does this).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

SettingsFactory = Callable[..., Settings]


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    if not TEST_DATABASE_URL:
        return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"

    engine = create_db_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        Base.metadata.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()
    return TEST_DATABASE_URL


@pytest.fixture
def make_settings(tmp_path: Path, database_url: str) -> SettingsFactory:
    def factory(*, embedded: bool = True) -> Settings:
        # _env_file=None: the developer's backend/.env (e.g. AUTH__REQUIRED=false) must not leak in.
        return Settings(
            _env_file=None,  # ty: ignore[unknown-argument]  (pydantic-settings kwarg)
            upscale=UpscaleSettings(backend="stub"),
            storage=StorageSettings(dir=tmp_path / "data"),
            image=ImageSettings(max_size_mb=1, max_width=256, max_height=256),
            video=VideoSettings(max_size_mb=1),
            database=DatabaseSettings(url=database_url),
            worker=WorkerSettings(embedded=embedded, poll_interval=0.01),
        )

    return factory


def register(
    client: TestClient,
    email: str = "anime@example.com",
    password: str = "secret-pass",
    name: str = "Анимешка",
) -> dict:
    """Creates an account; the client keeps the session cookie, so it is logged in after."""
    response = client.post(
        "/api/auth/register", json={"email": email, "password": password, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def client(make_settings: SettingsFactory) -> Iterator[TestClient]:
    """A logged-in client."""
    with TestClient(create_app(make_settings())) as test_client:
        register(test_client)
        yield test_client


def make_png(width: int = 64, height: int = 48) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def video_factory(tmp_path: Path) -> Callable[..., bytes]:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Video integration tests require FFmpeg and ffprobe")

    def create(*, audio: bool = False, fps: str = "12", duration: float = 0.5) -> bytes:
        path = tmp_path / "clip.mp4"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=64x48:rate={fps}:duration={duration}",
        ]
        if audio:
            command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)]
        subprocess.run(command, check=True, capture_output=True, timeout=30)
        return path.read_bytes()

    return create
