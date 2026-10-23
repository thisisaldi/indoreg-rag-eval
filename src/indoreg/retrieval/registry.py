"""Build retrievers by config name, so adding a variant is a config change (4.3)."""

from indoreg.config import BM25Spec, Settings
from indoreg.retrieval.base import Retriever
from indoreg.retrieval.bm25 import BM25Retriever
from indoreg.retrieval.dense import DenseRetriever, SentenceTransformerEncoder
from indoreg.retrieval.preprocess import TOKENIZERS


def build_retriever(name: str, settings: Settings) -> Retriever:
    spec = settings.retrieval.retrievers.get(name)
    if spec is None:
        raise ValueError(f"unknown retriever {name!r}")
    if isinstance(spec, BM25Spec):
        cfg = settings.retrieval.bm25
        return BM25Retriever(
            name,
            k1=cfg.k1,
            b=cfg.b,
            tokenizer=TOKENIZERS[spec.preprocess],
            index_title=spec.index_title,
        )
    encoder = SentenceTransformerEncoder(
        spec.model, spec.revision, spec.device, spec.batch_size, spec.max_seq_length
    )
    key = "|".join(
        [
            spec.model,
            spec.revision,
            spec.query_prefix,
            spec.passage_prefix,
            str(spec.max_seq_length),
        ]
    )
    return DenseRetriever(
        name,
        encoder,
        model_key=key,
        cache_dir=settings.paths.cache / "embeddings",
        query_prefix=spec.query_prefix,
        passage_prefix=spec.passage_prefix,
    )
