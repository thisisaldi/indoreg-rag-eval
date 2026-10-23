"""Build retrievers by config name, so adding a variant is a config change (4.3)."""

from indoreg.config import Settings
from indoreg.retrieval.base import Retriever
from indoreg.retrieval.bm25 import BM25Retriever
from indoreg.retrieval.preprocess import TOKENIZERS


def build_retriever(name: str, settings: Settings) -> Retriever:
    spec = settings.retrieval.retrievers.get(name)
    if spec is None:
        raise ValueError(f"unknown retriever {name!r}")
    cfg = settings.retrieval.bm25
    return BM25Retriever(
        name,
        k1=cfg.k1,
        b=cfg.b,
        tokenizer=TOKENIZERS[spec.preprocess],
        index_title=spec.index_title,
    )
