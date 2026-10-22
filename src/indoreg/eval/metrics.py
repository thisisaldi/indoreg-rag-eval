"""Per-query retrieval metrics over article units (design.md 4.5, FR-EVAL-4).

A ranking is a list of unit ids (for example "uu-27-2022:56"), best first.
Qrels map unit id -> grade (2 directly answers, 1 partially relevant).
A unit repeated in the ranking counts once, at its best rank (design.md 4.1).
Averaging over queries (for example MRR = mean reciprocal rank) is the runner's job.
"""

import math
from collections.abc import Mapping, Sequence

Ranking = Sequence[str]
Qrels = Mapping[str, int]


def _dedupe(ranking: Ranking) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for unit in ranking:
        if unit not in seen:
            seen.add(unit)
            out.append(unit)
    return out


def _relevant(qrels: Qrels) -> set[str]:
    rel = {u for u, g in qrels.items() if g > 0}
    if not rel:
        raise ValueError("query has no relevant units; every query needs one")
    return rel


def _check_k(k: int) -> None:
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")


def recall_at_k(ranking: Ranking, qrels: Qrels, k: int) -> float:
    """Fraction of relevant units (any grade > 0) found in the top k."""
    _check_k(k)
    rel = _relevant(qrels)
    return len(rel.intersection(_dedupe(ranking)[:k])) / len(rel)


def reciprocal_rank(ranking: Ranking, qrels: Qrels) -> float:
    """1 / rank of the first relevant unit; 0.0 if none is retrieved."""
    rel = _relevant(qrels)
    for rank, unit in enumerate(_dedupe(ranking), 1):
        if unit in rel:
            return 1.0 / rank
    return 0.0


def dcg(grades: Sequence[int]) -> float:
    """Graded gain 2^grade - 1 with log2(rank + 1) discount."""
    return sum((2.0**g - 1) / math.log2(rank + 1) for rank, g in enumerate(grades, 1))


def ndcg_at_k(ranking: Ranking, qrels: Qrels, k: int) -> float:
    """DCG of the top k divided by the DCG of the ideal top k."""
    _check_k(k)
    _relevant(qrels)
    gains = [qrels.get(u, 0) for u in _dedupe(ranking)[:k]]
    ideal = sorted((g for g in qrels.values() if g > 0), reverse=True)[:k]
    return dcg(gains) / dcg(ideal)
