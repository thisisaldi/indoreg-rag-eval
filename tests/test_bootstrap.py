import pytest

from indoreg.eval.bootstrap import bootstrap_ci, paired_diff_ci, win_loss


def test_ci_contains_mean_and_is_seeded() -> None:
    values = [0.0, 0.25, 0.5, 0.75, 1.0] * 4
    a = bootstrap_ci(values, iterations=1000, seed=42, confidence=0.95)
    b = bootstrap_ci(values, iterations=1000, seed=42, confidence=0.95)
    assert a is not None and a == b  # same seed, same interval
    assert a.mean == pytest.approx(0.5)
    assert 0.0 <= a.low < a.mean < a.high <= 1.0
    c = bootstrap_ci(values, iterations=1000, seed=7, confidence=0.95)
    assert c is not None and c.mean == a.mean


def test_constant_values_give_zero_width_interval() -> None:
    ci = bootstrap_ci([0.6] * 10, iterations=200, seed=1, confidence=0.95)
    assert ci is not None and ci.low == ci.high == pytest.approx(0.6)


def test_wider_confidence_gives_wider_interval() -> None:
    values = [0.0, 1.0] * 10
    narrow = bootstrap_ci(values, 2000, 3, 0.5)
    wide = bootstrap_ci(values, 2000, 3, 0.99)
    assert narrow is not None and wide is not None
    assert wide.high - wide.low > narrow.high - narrow.low


def test_empty_split_has_no_interval() -> None:
    assert bootstrap_ci([], 100, 1, 0.95) is None


def test_paired_difference_and_win_loss() -> None:
    a = [1.0, 1.0, 0.5, 0.0, 0.2]
    b = [0.0, 1.0, 0.5, 0.5, 0.2]
    d = paired_diff_ci(a, b, 500, 42, 0.95)
    assert d is not None and d.mean == pytest.approx(0.1)
    wl = win_loss(a, b)
    assert (wl.wins, wl.losses, wl.ties) == (1, 1, 3)
    # Identical systems: zero difference, all ties.
    same = paired_diff_ci(a, a, 500, 42, 0.95)
    assert same is not None and same.low == same.high == 0.0
    assert win_loss(a, a).ties == 5


def test_unpaired_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="paired"):
        win_loss([1.0], [1.0, 0.0])
    with pytest.raises(ValueError, match="paired"):
        paired_diff_ci([1.0], [1.0, 0.0], 10, 1, 0.95)
