"""BM25 (Okapi) over chunk text (FR-RET-1). Stdlib only (ADR-007).

Variants come from config: the tokenizer ("basic" or "id", see preprocess.py) and
whether the document title is indexed together with the chunk text.
"""

import heapq
import math
from array import array
from collections import Counter
from collections.abc import Callable, Sequence

from indoreg.retrieval.base import RetrievalResult
from indoreg.retrieval.preprocess import basic_tokens
from indoreg.schemas import Chunk

# Kept for callers that want the basic tokenizer directly.
tokenize = basic_tokens


class BM25Retriever:
    def __init__(
        self,
        name: str,
        k1: float,
        b: float,
        tokenizer: Callable[[str], list[str]] = basic_tokens,
        index_title: bool = False,
    ) -> None:
        self.name = name
        self.k1 = k1
        self.b = b
        self.tokenizer = tokenizer
        self.index_title = index_title
        self._ids: list[str] = []
        # term -> flat [chunk index, tf, chunk index, tf, ...]; compact for 700k+ chunks
        self._postings: dict[str, array[int]] = {}
        self._len: list[int] = []
        self._idf: dict[str, float] = {}
        self._avgdl = 0.0

    def build(self, chunks: Sequence[Chunk]) -> None:
        self._ids = [c.chunk_id for c in chunks]
        self._postings = {}
        self._len = []
        for i, c in enumerate(chunks):
            tf = Counter(
                self.tokenizer(f"{c.title}\n{c.text}" if self.index_title else c.text)
            )
            self._len.append(sum(tf.values()))
            for t, f in tf.items():
                self._postings.setdefault(t, array("I")).extend((i, f))
        n = len(chunks)
        self._avgdl = sum(self._len) / n if n else 0.0
        self._idf = {
            t: math.log(1 + (n - d + 0.5) / (d + 0.5))
            for t, d in ((t, len(p) // 2) for t, p in self._postings.items())
        }

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        # Inverted index: only chunks sharing a query term are scored.
        terms = sorted(t for t in set(self.tokenizer(query)) if t in self._idf)
        scores: dict[int, float] = {}
        for t in terms:
            idf = self._idf[t]
            p = self._postings[t]
            for i, f in zip(p[::2], p[1::2], strict=True):
                norm = self.k1 * (1 - self.b + self.b * self._len[i] / self._avgdl)
                scores[i] = scores.get(i, 0.0) + idf * f * (self.k1 + 1) / (f + norm)
        top = heapq.nsmallest(
            top_k,
            ((s, self._ids[i]) for i, s in scores.items() if s > 0),
            key=lambda x: (-x[0], x[1]),  # stable tie-break on chunk_id
        )
        return [
            RetrievalResult(chunk_id=cid, score=s, rank=r)
            for r, (s, cid) in enumerate(top, 1)
        ]
