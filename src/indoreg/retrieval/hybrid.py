"""Hybrid retrieval by reciprocal rank fusion (FR-RET-4, design.md 4.4).

score(chunk) = sum over members of 1 / (rrf_k + rank), over each member's top
`depth` results. Only ranks are fused, so member score scales do not matter.
"""

from collections import defaultdict
from collections.abc import Sequence

from indoreg.retrieval.base import RetrievalResult, Retriever
from indoreg.schemas import Chunk


class HybridRetriever:
    def __init__(
        self, name: str, members: Sequence[Retriever], rrf_k: float, depth: int
    ) -> None:
        self.name = name
        self.members = list(members)
        self.rrf_k = rrf_k
        self.depth = depth

    def build(self, chunks: Sequence[Chunk]) -> None:
        for m in self.members:
            m.build(chunks)

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        return rrf([m.search(query, self.depth) for m in self.members], self.rrf_k)[
            :top_k
        ]


def rrf(
    rankings: Sequence[Sequence[RetrievalResult]], k: float
) -> list[RetrievalResult]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for hit in ranking:
            scores[hit.chunk_id] += 1.0 / (k + hit.rank)
    fused = sorted(scores.items(), key=lambda x: (-x[1], x[0]))  # tie: chunk_id
    return [
        RetrievalResult(chunk_id=cid, score=s, rank=r)
        for r, (cid, s) in enumerate(fused, 1)
    ]
