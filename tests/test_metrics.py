"""Metrics against hand-computed values (T-12)."""

import math

import pytest

from indoreg.eval.metrics import dcg, ndcg_at_k, recall_at_k, reciprocal_rank

QRELS = {"a": 2, "b": 1, "c": 2}
# Relevant units sit at ranks 2 (a, grade 2), 4 (b, grade 1) and 6 (c, grade 2).
RANKING = ["x", "a", "y", "b", "z", "c"]

# By hand: DCG@5 = (2^2-1)/log2(3) + (2^1-1)/log2(5) = 1.892789 + 0.430677 = 2.323466
#          IDCG@5 over grades [2, 2, 1] = 3/1 + 3/log2(3) + 1/log2(4) = 5.392789
NDCG5 = 2.323466 / 5.392789  # 0.430847


def test_recall_at_k() -> None:
    assert recall_at_k(RANKING, QRELS, 1) == 0.0
    assert recall_at_k(RANKING, QRELS, 2) == pytest.approx(1 / 3)
    assert recall_at_k(RANKING, QRELS, 5) == pytest.approx(2 / 3)
    assert recall_at_k(RANKING, QRELS, 6) == 1.0


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(RANKING, QRELS) == 0.5
    assert reciprocal_rank(["c", "x"], QRELS) == 1.0
    assert reciprocal_rank(["x", "y"], QRELS) == 0.0


def test_dcg_hand_values() -> None:
    assert dcg([0, 2, 0, 1, 0]) == pytest.approx(2.323466, abs=1e-6)
    assert dcg([2, 2, 1]) == pytest.approx(5.392789, abs=1e-6)
    assert dcg([]) == 0.0


def test_ndcg_at_k() -> None:
    assert ndcg_at_k(RANKING, QRELS, 5) == pytest.approx(NDCG5, abs=1e-6)
    assert ndcg_at_k(["a", "c", "b"], QRELS, 10) == pytest.approx(1.0)
    # Ideal order among equal grades does not matter.
    assert ndcg_at_k(["c", "a", "b"], QRELS, 10) == pytest.approx(1.0)
    assert ndcg_at_k(["b", "a", "c"], QRELS, 10) < 1.0


def test_k_larger_than_results() -> None:
    assert recall_at_k(["a"], QRELS, 10) == pytest.approx(1 / 3)
    assert ndcg_at_k(["a"], QRELS, 10) == pytest.approx(3 / 5.392789, abs=1e-6)
    assert recall_at_k([], QRELS, 10) == 0.0
    assert ndcg_at_k([], QRELS, 10) == 0.0


def test_duplicate_units_count_once_at_best_rank() -> None:
    # Two chunks of the same article must not double its gain.
    assert recall_at_k(["a", "a", "b"], QRELS, 2) == pytest.approx(2 / 3)
    assert ndcg_at_k(["a", "a"], QRELS, 10) == ndcg_at_k(["a"], QRELS, 10)
    assert reciprocal_rank(["x", "a", "x", "a"], QRELS) == 0.5


def test_grade_zero_and_unknown_units_are_not_relevant() -> None:
    qrels = {"a": 2, "n": 0}
    assert recall_at_k(["n", "a"], qrels, 1) == 0.0
    assert reciprocal_rank(["n", "a"], qrels) == 0.5
    assert ndcg_at_k(["n", "a"], qrels, 2) == pytest.approx(1 / math.log2(3))


@pytest.mark.parametrize("qrels", [{}, {"a": 0}])
def test_no_relevant_units_is_an_error(qrels: dict[str, int]) -> None:
    for call in (
        lambda: recall_at_k(["a"], qrels, 5),
        lambda: reciprocal_rank(["a"], qrels),
        lambda: ndcg_at_k(["a"], qrels, 5),
    ):
        with pytest.raises(ValueError, match="no relevant"):
            call()


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError, match="k must be"):
        recall_at_k(RANKING, QRELS, 0)
    with pytest.raises(ValueError, match="k must be"):
        ndcg_at_k(RANKING, QRELS, 0)
