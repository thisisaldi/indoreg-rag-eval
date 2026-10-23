"""Settings loaded from a YAML file, overridable by INDOREG_ environment variables.

Every value comes from the YAML file: models have no defaults, so a missing key
fails at load time instead of silently falling back.
"""

import os
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]  # stubs (types-PyYAML) not a dependency
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    ValidationError,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

DEFAULT_CONFIG = Path("configs/default.yaml")
CONFIG_ENV_VAR = "INDOREG_CONFIG"


class ConfigError(Exception):
    """Configuration file missing, unreadable, or invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PathsConfig(_Strict):
    raw: Path
    manifest: Path
    dataset: Path
    processed: Path
    chunks: Path
    cache: Path
    results: Path


class FixedChunkingConfig(_Strict):
    size_chars: PositiveInt
    overlap_chars: NonNegativeInt

    @model_validator(mode="after")
    def _overlap_below_size(self) -> "FixedChunkingConfig":
        if self.overlap_chars >= self.size_chars:
            raise ValueError("overlap_chars must be smaller than size_chars")
        return self


class ChunkingConfig(_Strict):
    fixed: FixedChunkingConfig


class LoggingConfig(_Strict):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    log_query_text: bool


class BM25Config(_Strict):
    k1: PositiveFloat
    b: float = Field(ge=0, le=1)


class RetrievalConfig(_Strict):
    bm25: BM25Config


Strategy = Literal["article", "fixed"]


class SearchConfig(_Strict):
    default_top_k: PositiveInt
    max_top_k: PositiveInt
    strategy: Strategy  # chunk strategy served by search

    @model_validator(mode="after")
    def _default_within_max(self) -> "SearchConfig":
        if self.default_top_k > self.max_top_k:
            raise ValueError("default_top_k must not exceed max_top_k")
        return self


class EvalConfig(_Strict):
    retrievers: list[str] = Field(min_length=1)
    strategies: list[Strategy] = Field(min_length=1)
    splits: list[Literal["dev", "test"]] = Field(min_length=1)
    recall_ks: list[PositiveInt] = Field(min_length=1)
    ndcg_k: PositiveInt
    depth: PositiveInt  # chunks retrieved per query before mapping to articles

    @model_validator(mode="after")
    def _depth_covers_k(self) -> "EvalConfig":
        if self.depth < max(*self.recall_ks, self.ndcg_k):
            raise ValueError("depth must be at least the largest k")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INDOREG_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    paths: PathsConfig
    chunking: ChunkingConfig
    logging: LoggingConfig
    retrieval: RetrievalConfig
    search: SearchConfig
    eval: EvalConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Environment first so it overrides the YAML values passed as init kwargs.
        return (env_settings, init_settings)


def load_settings(config_path: Path | None = None) -> Settings:
    """Load from config_path, else $INDOREG_CONFIG, else configs/default.yaml."""
    path = config_path or Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG))
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    try:
        return Settings(**data)
    except ValidationError as e:
        raise ConfigError(f"invalid configuration in {path}:\n{e}") from e
