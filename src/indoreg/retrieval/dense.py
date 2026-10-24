"""Dense retrieval (FR-RET-2): brute-force cosine over a numpy matrix (ADR-003).

Chunk embeddings are cached under the cache dir, keyed by the model identity and
a hash of the chunk ids and texts, so a changed chunk file never reuses vectors.
The model is only downloaded and loaded when an OnnxEncoder is built, so tests
run with a stub encoder and no model files.
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


def model_file(model: str, revision: str, filename: str, model_dir: Path) -> Path:
    """Path of a model file as a plain file under model_dir (no cache symlinks),
    so the directory can be bundled by Docker or Vercel (ADR-019). A file already
    there is used as is: the revision is part of the directory name, and the hub
    client would try to write a lock file, which fails on a read-only deployment.
    """
    local = model_dir / f"{model.replace('/', '__')}@{revision}"
    path = local / filename
    if path.is_file():
        return path
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(model, filename, revision=revision, local_dir=local))


class OnnxEncoder:
    """Transformer encoder run with onnxruntime: mean pooling over the attention
    mask, then L2 normalisation (the E5 recipe). No torch, so it fits a small
    serverless function (ADR-016)."""

    def __init__(
        self,
        model: str,
        revision: str,
        onnx_file: str,
        batch_size: int,
        max_seq_length: int,
        model_dir: Path,
    ) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        def fetch(filename: str) -> str:
            return str(model_file(model, revision, filename, model_dir))

        self._tokenizer = Tokenizer.from_file(fetch("tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=max_seq_length)
        self._tokenizer.enable_padding()
        self._session = ort.InferenceSession(
            fetch(onnx_file), providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}
        self._batch_size = batch_size

    def encode(self, texts: list[str]) -> Matrix:
        # Batches of similar length pad less: about 3x faster on CPU. Rows are
        # put back in input order.
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = [
            self._encode_batch([texts[j] for j in order[i : i + self._batch_size]])
            for i in range(0, len(texts), self._batch_size)
        ]
        if not out:
            return np.zeros((0, 0), dtype=np.float32)
        sorted_rows = np.concatenate(out)
        rows = np.empty_like(sorted_rows)
        rows[order] = sorted_rows
        return rows

    def _encode_batch(self, texts: list[str]) -> Matrix:
        enc = self._tokenizer.encode_batch(texts)
        feed = {
            "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in enc], dtype=np.int64),
        }
        hidden = self._session.run(
            None, {k: v for k, v in feed.items() if k in self._inputs}
        )[0]
        return mean_pool_normalise(
            np.asarray(hidden, dtype=np.float32), feed["attention_mask"]
        )


def mean_pool_normalise(hidden: Matrix, mask: npt.NDArray[np.int64]) -> Matrix:
    """(batch, tokens, dim) hidden states to (batch, dim) unit vectors."""
    m = mask[:, :, None].astype(np.float32)
    pooled = (hidden * m).sum(axis=1) / np.maximum(m.sum(axis=1), 1e-9)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    return (pooled / np.maximum(norms, 1e-12)).astype(np.float32)


class DenseRetriever:
    def __init__(
        self,
        name: str,
        encoder: Encoder,
        model_key: str,
        cache_dir: Path,
        query_prefix: str = "",
        passage_prefix: str = "",
        shard_size: int = 20_000,
    ) -> None:
        self.name = name
        self.shard_size = shard_size  # chunks per resumable part file
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
            self._matrix = self._encode_resumable(chunks, path)
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

    def _encode_resumable(self, chunks: Sequence[Chunk], path: Path) -> Matrix:
        """Encode in parts saved next to the cache file, so a long run (700k+
        chunks take hours on CPU) resumes after a crash. Parts are deleted once
        the full matrix is saved."""
        parts_dir = path.with_suffix(".parts")
        parts_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Matrix] = []
        for n, i in enumerate(range(0, len(chunks), self.shard_size)):
            part = parts_dir / f"{n:05d}.npy"
            if part.is_file():
                parts.append(np.load(part))
                continue
            batch = chunks[i : i + self.shard_size]
            m = self.encoder.encode([self.passage_prefix + c.text for c in batch])
            np.save(part, m)
            parts.append(m)
            log.info(
                "dense part encoded",
                extra={
                    "fields": {
                        "name": self.name,
                        "done": i + len(batch),
                        "total": len(chunks),
                    }
                },
            )
        matrix = np.concatenate(parts) if parts else np.zeros((0, 0), dtype=np.float32)
        np.save(path, matrix)
        for part in sorted(parts_dir.glob("*.npy")):
            part.unlink()
        parts_dir.rmdir()
        return matrix

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        if not self._ids or top_k <= 0:
            return []
        q = self.encoder.encode([self.query_prefix + query])[0]
        scores = self._matrix @ q
        # Partial sort: keep every chunk scoring at least the k-th best, so the
        # chunk_id tie-break below sees all ties at the cut.
        k = min(top_k, len(self._ids))
        kth = np.partition(scores, len(scores) - k)[len(scores) - k]
        cand = np.flatnonzero(scores >= kth)
        ranked = sorted(
            ((float(scores[i]), self._ids[i]) for i in cand.tolist()), key=_order
        )
        return [
            RetrievalResult(chunk_id=cid, score=s, rank=r)
            for r, (s, cid) in enumerate(ranked[:top_k], 1)
        ]


def _order(pair: tuple[float, str]) -> tuple[float, str]:
    return (-pair[0], pair[1])  # stable tie-break on chunk_id
