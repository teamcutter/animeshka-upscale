import os
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
        return Settings(
            upscale=UpscaleSettings(backend="stub"),
            storage=StorageSettings(dir=tmp_path / "data"),
            image=ImageSettings(max_size_mb=1, max_width=256, max_height=256),
            database=DatabaseSettings(url=database_url),
            worker=WorkerSettings(embedded=embedded, poll_interval=0.01),
        )

    return factory


@pytest.fixture
def client(make_settings: SettingsFactory) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


def make_png(width: int = 64, height: int = 48) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()
