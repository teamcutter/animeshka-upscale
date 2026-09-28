from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yml"


class AppSettings(BaseModel):
    title: str = "Animeshka Upscale API"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


class UpscaleSettings(BaseModel):
    model_path: Path = Path("./weights/upscale_model")
    tile_size: int = Field(default=512, ge=64, le=2048)
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    scale: int = Field(default=2, ge=1, le=4)

    @property
    def resolved_model_path(self) -> Path:
        if self.model_path.is_absolute():
            return self.model_path
        return (CONFIG_PATH.parent / self.model_path).resolve()


class ImageSettings(BaseModel):
    max_size_mb: int = Field(default=10, ge=1)
    max_width: int = Field(default=2048, ge=1)
    max_height: int = Field(default=2048, ge=1)


class VideoSettings(BaseModel):
    max_size_mb: int = Field(default=200, ge=1)


class StorageSettings(BaseModel):
    dir: Path = Path("./data")


class LogSettings(BaseModel):
    level: str = "INFO"
    file: str | None = None


class Settings(BaseSettings):
    """Priority: init args > env > .env > config.yml > file secrets > defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        yaml_file=CONFIG_PATH,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    upscale: UpscaleSettings = Field(default_factory=UpscaleSettings)
    image: ImageSettings = Field(default_factory=ImageSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    log: LogSettings = Field(default_factory=LogSettings)
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
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
