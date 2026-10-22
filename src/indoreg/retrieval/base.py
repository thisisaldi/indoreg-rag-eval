"""Shared retriever interface (design.md 4.3): eval runner and API use the same one."""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from indoreg.schemas import Chunk


class RetrievalResult(BaseModel):
    chunk_id: str
    score: float
    rank: int


class Retriever(Protocol):
    name: str

    def build(self, chunks: Sequence[Chunk]) -> None: ...

    def search(self, query: str, top_k: int) -> list[RetrievalResult]: ...
