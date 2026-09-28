from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yml"


class YamlSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        value = self._data.get(field_name)
        return value, field_name, isinstance(value, dict)

    def __call__(self) -> dict[str, Any]:
        return self._data


class UpscaleConfig(BaseModel):
    model_path: str = Field(default="./weights/upscale_model")
    tile_size: int = Field(default=512, ge=64, le=2048)
    device: str = Field(default="auto", description="auto|cuda|mps|cpu")
    scale: int = Field(default=2, ge=1, le=4)

    @property
    def resolved_model_path(self) -> Path:
        p = Path(self.model_path)
        if not p.is_absolute():
            p = (CONFIG_PATH.parent / p).resolve()
        return p


class ImageConfig(BaseModel):
    max_size_mb: int = Field(default=10, ge=1)
    max_width: int = Field(default=2048, ge=1)
    max_height: int = Field(default=2048, ge=1)


class LogConfig(BaseModel):
    level: str = Field(default="INFO")
    file: str | None = Field(default=None)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    upscale: UpscaleConfig = Field(default_factory=UpscaleConfig)
    image: ImageConfig = Field(default_factory=ImageConfig)
    log: LogConfig = Field(default_factory=LogConfig)

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
            YamlSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
