"""Dense retrieval (FR-RET-2): brute-force cosine over a numpy matrix (ADR-003).

Chunk embeddings are cached under the cache dir, keyed by the model identity and
a hash of the chunk ids and texts, so a changed chunk file never reuses vectors.
The sentence-transformers import is deferred to SentenceTransformerEncoder, so
this module and its tests run without the optional `dense` extra.
"""

import hashlib
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from indoreg.logging import get_logger
from indoreg.retrieval.base import RetrievalResult
from indoreg.schemas import Chunk

log = get_logger(__name__)

Matrix = npt.NDArray[np.float32]


class Encoder(Protocol):
    def encode(self, texts: list[str]) -> Matrix:
        """Return one L2-normalised row per text."""
        ...


class SentenceTransformerEncoder:
    def __init__(
        self, model: str, revision: str, device: str, batch_size: int, max_seq: int
    ) -> None:
        from sentence_transformers import SentenceTransformer  # optional extra

        self._model = SentenceTransformer(model, revision=revision, device=device)
        self._model.max_seq_length = max_seq
        self._batch_size = batch_size

    def encode(self, texts: list[str]) -> Matrix:
        out = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(out, dtype=np.float32)


class DenseRetriever:
    def __init__(
        self,
        name: str,
        encoder: Encoder,
        model_key: str,
        cache_dir: Path,
        query_prefix: str = "",
        passage_prefix: str = "",
    ) -> None:
        self.name = name
        self.encoder = encoder
        self.model_key = model_key  # model name + revision + prefixes
        self.cache_dir = cache_dir
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self._ids: list[str] = []
        self._matrix: Matrix = np.zeros((0, 0), dtype=np.float32)
        self.stats: dict[str, Any] = {}

    def cache_path(self, chunks: Sequence[Chunk]) -> Path:
        h = hashlib.sha256(self.model_key.encode("utf-8"))
        for c in chunks:
            h.update(f"\0{c.chunk_id}\0{c.text}".encode())
        return self.cache_dir / f"{h.hexdigest()}.npy"

    def build(self, chunks: Sequence[Chunk]) -> None:
        self._ids = [c.chunk_id for c in chunks]
        path = self.cache_path(chunks)
        start = time.perf_counter()
        hit = path.is_file()
        if hit:
            self._matrix = np.load(path)
        else:
            self._matrix = self.encoder.encode(
                [self.passage_prefix + c.text for c in chunks]
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, self._matrix)
        if self._matrix.shape[0] != len(chunks):
            raise ValueError(
                f"{path}: {self._matrix.shape[0]} vectors for {len(chunks)} chunks"
            )
        self.stats = {
            "cache_hit": hit,
            "embed_seconds": round(time.perf_counter() - start, 3),
            "index_bytes": int(self._matrix.nbytes),
            "dim": int(self._matrix.shape[1]) if self._matrix.ndim == 2 else 0,
        }
        log.info(
            "dense index built", extra={"fields": {"name": self.name, **self.stats}}
        )

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        if not self._ids:
            return []
        q = self.encoder.encode([self.query_prefix + query])[0]
        scores = self._matrix @ q
        ranked = sorted(zip(scores.tolist(), self._ids, strict=True), key=_order)
        return [
            RetrievalResult(chunk_id=cid, score=s, rank=r)
            for r, (s, cid) in enumerate(ranked[:top_k], 1)
        ]


def _order(pair: tuple[float, str]) -> tuple[float, str]:
    return (-pair[0], pair[1])  # stable tie-break on chunk_id
