"""Bootstrap confidence intervals and per-query win/loss (design.md 4.5, FR-EVAL-5).

Queries are resampled with replacement; the interval is the percentile interval
of the resampled means. Comparisons are paired: both systems are evaluated on the
same resampled queries, so the interval is on the per-query difference.
"""

import random
from collections.abc import Sequence
from statistics import mean

from pydantic import BaseModel


class Interval(BaseModel):
    mean: float
    low: float
    high: float


class WinLoss(BaseModel):
    wins: int
    losses: int
    ties: int


def _percentile_interval(
    samples: list[float], confidence: float
) -> tuple[float, float]:
    samples.sort()
    alpha = (1 - confidence) / 2
    lo = samples[int(alpha * len(samples))]
    hi = samples[min(len(samples) - 1, int((1 - alpha) * len(samples)))]
    return lo, hi


def bootstrap_ci(
    values: Sequence[float], iterations: int, seed: int, confidence: float
) -> Interval | None:
    """Percentile CI of the mean; None for an empty split."""
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = [
        mean(values[i] for i in rng.choices(range(n), k=n)) for _ in range(iterations)
    ]
    lo, hi = _percentile_interval(means, confidence)
    return Interval(mean=mean(values), low=lo, high=hi)


def paired_diff_ci(
    a: Sequence[float],
    b: Sequence[float],
    iterations: int,
    seed: int,
    confidence: float,
) -> Interval | None:
    """CI of mean(a - b) over paired queries."""
    if len(a) != len(b):
        raise ValueError("paired comparison needs the same queries in the same order")
    return bootstrap_ci(
        [x - y for x, y in zip(a, b, strict=True)], iterations, seed, confidence
    )


def win_loss(a: Sequence[float], b: Sequence[float], eps: float = 1e-12) -> WinLoss:
    """Per-query wins/losses/ties of a over b."""
    if len(a) != len(b):
        raise ValueError("paired comparison needs the same queries in the same order")
    wins = sum(1 for x, y in zip(a, b, strict=True) if x > y + eps)
    losses = sum(1 for x, y in zip(a, b, strict=True) if x < y - eps)
    return WinLoss(wins=wins, losses=losses, ties=len(a) - wins - losses)
