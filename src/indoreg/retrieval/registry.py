"""Build retrievers by config name, so adding a variant is a config change (4.3)."""

from indoreg.config import Settings
from indoreg.retrieval.base import Retriever
from indoreg.retrieval.bm25 import BM25Retriever


def build_retriever(name: str, settings: Settings) -> Retriever:
    if name == "bm25-basic":
        cfg = settings.retrieval.bm25
        return BM25Retriever(name, k1=cfg.k1, b=cfg.b)
    raise ValueError(f"unknown retriever {name!r}")
