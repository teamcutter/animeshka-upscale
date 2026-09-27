from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class AppSettings(BaseModel):
    title: str = "Animeshka Upscale API"
    host: str = "0.0.0.0"
    port: int = 8000


class UpscaleSettings(BaseModel):
    model_path: Path = Path("./weights/upscale_model")
    tile_size: int = 512
    device: Literal["cuda", "cpu"] = "cpu"


class ImageSettings(BaseModel):
    max_size_mb: int = 10
    max_width: int = 2048
    max_height: int = 2048


class VideoSettings(BaseModel):
    max_size_mb: int = 200


class StorageSettings(BaseModel):
    dir: Path = Path("./data")


class LogSettings(BaseModel):
    level: str = "INFO"


class Settings(BaseSettings):
    """Priority: init args > env > .env > config.yml > defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        yaml_file="config.yml",
        extra="ignore",
    )

    app: AppSettings = AppSettings()
    upscale: UpscaleSettings = UpscaleSettings()
    image: ImageSettings = ImageSettings()
    video: VideoSettings = VideoSettings()
    storage: StorageSettings = StorageSettings()
    log: LogSettings = LogSettings()
    database_url: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
        )
