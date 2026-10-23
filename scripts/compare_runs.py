"""Paired comparison of the same runs across two result files (before / after).

Uses the per-query metrics stored in both files and the project's bootstrap
(indoreg.eval.bootstrap), with the bootstrap settings of the `after` file.
Refuses to compare files built on different datasets.

Usage:
  uv run python scripts/compare_runs.py before.json after.json \
      --runs hybrid/article bm25-id-title/article > out.md
"""

import argparse
import json
from pathlib import Path

from indoreg.eval.bootstrap import paired_diff_ci, win_loss


def cell(a: list[float], b: list[float], boot: dict) -> str:
    d = paired_diff_ci(a, b, boot["iterations"], boot["seed"], boot["confidence"])
    wl = win_loss(a, b)
    if d is None:
        return "n/a"
    return (
        f"{d.mean:+.3f} [{d.low:+.2f}, {d.high:+.2f}] {wl.wins}/{wl.losses}/{wl.ties}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--runs", nargs="+", required=True)
    args = ap.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    if before["dataset"]["sha256"] != after["dataset"]["sha256"]:
        raise SystemExit("different datasets; refusing to compare")
    boot, keys = after["bootstrap"], after["metric_keys"]
    print(f"# {after['run_id']} vs {before['run_id']}\n")
    print(
        f"Per-query difference after minus before, mean [{boot['confidence']:.0%}"
        f" bootstrap CI] and wins/losses/ties ({boot['iterations']} resamples,"
        f" seed {boot['seed']}). A CI that includes 0 is not established.\n"
    )
    for split in after["results"]:
        print(f"## {split}\n")
        print("| run | " + " | ".join(keys) + " |")
        print("|" + "---|" * (len(keys) + 1))
        for run in args.runs:
            new = after["results"][split][run]["queries"]
            old = before["results"][split][run]["queries"]
            if [q["query_id"] for q in new] != [q["query_id"] for q in old]:
                raise SystemExit(f"{split} {run}: query order differs")
            cells = [cell([q[k] for q in new], [q[k] for q in old], boot) for k in keys]
            print(f"| {run} | " + " | ".join(cells) + " |")
        print()


if __name__ == "__main__":
    main()
