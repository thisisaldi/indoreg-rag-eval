"""Settings loaded from a YAML file, overridable by INDOREG_ environment variables.

Every value comes from the YAML file: models have no defaults, so a missing key
fails at load time instead of silently falling back.
"""

import os
from pathlib import Path
from typing import Annotated, Any, Literal

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
    models: Path  # model files as plain files (no symlinks), ADR-019
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


class BM25Spec(_Strict):
    """A named BM25 variant (design.md 4.3: a new variant is a config change)."""

    type: Literal["bm25"]
    preprocess: Literal["basic", "id"]
    index_title: bool


class DenseSpec(_Strict):
    """A named dense model run with onnxruntime (FR-RET-2, ADR-016); a new model
    is a config change (FR-RET-3)."""

    type: Literal["dense"]
    model: str  # Hugging Face repo id
    revision: str  # pinned model commit, recorded in every result file
    onnx_file: str  # path of the ONNX graph inside the repo
    query_prefix: str
    passage_prefix: str
    max_seq_length: PositiveInt
    batch_size: PositiveInt


class HybridSpec(_Strict):
    """Reciprocal rank fusion over named member retrievers (FR-RET-4)."""

    type: Literal["hybrid"]
    members: list[str] = Field(min_length=2)  # names of non-hybrid retrievers
    rrf_k: PositiveFloat
    depth: PositiveInt  # results taken from each member before fusing


RetrieverSpec = Annotated[
    BM25Spec | DenseSpec | HybridSpec, Field(discriminator="type")
]


class RetrievalConfig(_Strict):
    bm25: BM25Config
    retrievers: dict[str, RetrieverSpec] = Field(min_length=1)


Strategy = Literal["article", "fixed"]


class SearchConfig(_Strict):
    default_top_k: PositiveInt
    max_top_k: PositiveInt
    max_query_chars: PositiveInt  # after stripping whitespace (FR-API-3)
    cors_origins: list[str]  # browser origins allowed to call the API
    retriever: str  # name in retrieval.retrievers
    strategy: Strategy  # chunk strategy served by search

    @model_validator(mode="after")
    def _default_within_max(self) -> "SearchConfig":
        if self.default_top_k > self.max_top_k:
            raise ValueError("default_top_k must not exceed max_top_k")
        return self


class BootstrapConfig(_Strict):
    iterations: PositiveInt
    seed: int
    confidence: float = Field(gt=0, lt=1)


class EvalConfig(_Strict):
    retrievers: list[str] = Field(min_length=1)
    strategies: list[Strategy] = Field(min_length=1)
    baseline: str  # "<retriever>/<strategy>" every run is compared with
    pairs: list[tuple[str, str]]  # extra paired comparisons (run, reference)
    bootstrap: BootstrapConfig
    splits: list[Literal["dev", "test"]] = Field(min_length=1)
    recall_ks: list[PositiveInt] = Field(min_length=1)
    ndcg_k: PositiveInt
    depth: PositiveInt  # chunks retrieved per query before mapping to articles

    @model_validator(mode="after")
    def _depth_covers_k(self) -> "EvalConfig":
        if self.depth < max(*self.recall_ks, self.ndcg_k):
            raise ValueError("depth must be at least the largest k")
        for run in [self.baseline, *(r for pair in self.pairs for r in pair)]:
            name, _, strategy = run.partition("/")
            if name not in self.retrievers or strategy not in self.strategies:
                raise ValueError(
                    f"{run!r} must be '<retriever>/<strategy>' from"
                    " eval.retrievers and eval.strategies"
                )
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

    @model_validator(mode="after")
    def _retriever_names_exist(self) -> "Settings":
        known = self.retrieval.retrievers
        unknown = [
            n for n in [*self.eval.retrievers, self.search.retriever] if n not in known
        ]
        if unknown:
            raise ValueError(
                f"retrievers not defined in retrieval.retrievers: {unknown}"
            )
        for name, spec in known.items():
            if isinstance(spec, HybridSpec):
                bad = [
                    m
                    for m in spec.members
                    if m not in known or isinstance(known[m], HybridSpec)
                ]
                if bad:
                    raise ValueError(
                        f"hybrid {name!r} members must be defined, non-hybrid"
                        f" retrievers: {bad}"
                    )
        return self

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
