"""Load and validate the labeled query set (design.md 3.4, eval/LABELING.md)."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

QueryType = Literal["exact_ref", "paraphrase", "terminology", "mixed_id_en"]
Split = Literal["dev", "test"]
MAX_LABELS = 5


class DatasetError(Exception):
    """The dataset file is missing or has invalid records."""


class Label(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(min_length=1)
    article: str = Field(min_length=1)
    grade: int = Field(ge=1, le=2)

    @property
    def unit(self) -> str:
        return f"{self.doc_id}:{self.article}"


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    type: QueryType
    split: Split
    relevant: list[Label] = Field(min_length=1, max_length=MAX_LABELS)
    source_note: str
    version: int = Field(ge=1)
    draft_status: str | None = None  # only on LLM drafts (ADR-014)

    @model_validator(mode="after")
    def _has_direct_answer(self) -> "Query":
        if not any(lb.grade == 2 for lb in self.relevant):
            raise ValueError("needs at least one grade-2 label")
        if len({lb.unit for lb in self.relevant}) != len(self.relevant):
            raise ValueError("duplicate label")
        return self

    @property
    def qrels(self) -> dict[str, int]:
        return {lb.unit: lb.grade for lb in self.relevant}


def load_dataset(path: Path, allow_drafts: bool = False) -> list[Query]:
    """Parse every line; report all problems at once. Drafts need allow_drafts."""
    if not path.is_file():
        raise DatasetError(f"dataset not found: {path}")
    queries: list[Query] = []
    errors: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            q = Query.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as e:
            errors.append(f"line {n}: {e}")
            continue
        if q.draft_status is not None and not allow_drafts:
            errors.append(f"line {n}: {q.query_id} is an unverified draft")
        queries.append(q)
    seen: set[str] = set()
    for q in queries:
        if q.query_id in seen:
            errors.append(f"duplicate query_id {q.query_id}")
        seen.add(q.query_id)
    if errors:
        raise DatasetError(f"{path}: {len(errors)} problem(s)\n" + "\n".join(errors))
    return queries
