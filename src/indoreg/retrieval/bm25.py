"""BM25 (Okapi) over chunk text with a basic tokenizer (FR-RET-1, basic variant).

Stdlib only; library choice in ADR-007 is still open.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence

from indoreg.retrieval.base import RetrievalResult
from indoreg.schemas import Chunk

WORD = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return WORD.findall(text.lower())


class BM25Retriever:
    def __init__(self, name: str, k1: float, b: float) -> None:
        self.name = name
        self.k1 = k1
        self.b = b
        self._ids: list[str] = []
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []
        self._idf: dict[str, float] = {}
        self._avgdl = 0.0

    def build(self, chunks: Sequence[Chunk]) -> None:
        self._ids = [c.chunk_id for c in chunks]
        self._tf = [Counter(tokenize(c.text)) for c in chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        n = len(chunks)
        self._avgdl = sum(self._len) / n if n else 0.0
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        # ponytail: scores every chunk per query; fine below ~10k chunks (ADR-003).
        terms = [t for t in set(tokenize(query)) if t in self._idf]
        scored: list[tuple[float, str]] = []
        for i, tf in enumerate(self._tf):
            norm = self.k1 * (1 - self.b + self.b * self._len[i] / self._avgdl)
            s = sum(
                self._idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + norm)
                for t in terms
                if t in tf
            )
            if s > 0:
                scored.append((s, self._ids[i]))
        scored.sort(key=lambda x: (-x[0], x[1]))  # stable tie-break on chunk_id
        return [
            RetrievalResult(chunk_id=cid, score=s, rank=r)
            for r, (s, cid) in enumerate(scored[:top_k], 1)
        ]
