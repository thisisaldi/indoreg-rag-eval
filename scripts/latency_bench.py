"""Serving latency per retriever, cold and warm (T-27, NFR7, FR-EVAL-8).

Each retriever runs in its own fresh Python process, so "cold" includes imports,
loading chunks, loading the model and the embedding cache from disk, and the
first request. "Warm" then sends the dataset queries `--rounds` times through
the FastAPI app in-process (Starlette TestClient: full request handling,
validation and JSON, but no network socket), after `--warmup` discarded
requests. The embedding cache must already exist (run `make eval` first),
as it does in the Docker image.

Usage:
  uv run python scripts/latency_bench.py \
      --retrievers bm25-basic bm25-id-title dense-e5-small hybrid
Writes reports/results/<timestamp>-<sha>-latency.{json,md}.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime

T0 = time.perf_counter()  # process start, as close as possible


def worker(retriever: str, rounds: int, warmup: int) -> None:
    os.environ["INDOREG_SEARCH__RETRIEVER"] = retriever
    from fastapi.testclient import TestClient

    from indoreg.api.app import create_app
    from indoreg.config import load_settings
    from indoreg.eval.dataset import load_dataset

    settings = load_settings()
    queries = [q.query for q in load_dataset(settings.paths.dataset)]
    with TestClient(create_app(settings)) as client:  # lifespan builds the index
        ready = time.perf_counter()
        t = time.perf_counter()
        client.post("/search", json={"query": queries[0]}).raise_for_status()
        first = time.perf_counter()
        first_ms = (first - t) * 1000
        warm: list[float] = []
        for i in range(warmup + rounds * len(queries)):
            q = queries[i % len(queries)]
            t = time.perf_counter()
            r = client.post("/search", json={"query": q})
            ms = (time.perf_counter() - t) * 1000
            r.raise_for_status()
            if i >= warmup:
                warm.append(ms)
    print(
        json.dumps(
            {
                "retriever": retriever,
                "startup_ms": (ready - T0) * 1000,
                "first_request_ms": first_ms,
                "cold_total_ms": (first - T0) * 1000,
                "warm_ms": warm,
            }
        )
    )


def main() -> None:
    from indoreg.config import load_settings
    from indoreg.eval.runner import git_state, percentile

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--retrievers", nargs="+", required=True)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--worker", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.worker:
        worker(args.worker, args.rounds, args.warmup)
        return

    rows = []
    for name in args.retrievers:
        out = (
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--retrievers",
                    name,
                    "--worker",
                    name,
                    "--rounds",
                    str(args.rounds),
                    "--warmup",
                    str(args.warmup),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
            .splitlines()[-1]
        )
        r = json.loads(out)
        w = r.pop("warm_ms")
        r.update(
            warm_n=len(w),
            warm_p50_ms=percentile(w, 50),
            warm_p95_ms=percentile(w, 95),
            warm_max_ms=max(w),
        )
        rows.append(r)

    import onnxruntime

    git = git_state()
    now = datetime.now(UTC)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + f"-{git['sha'][:7]}-latency"
    result = {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "git": git,
        "method": __doc__,
        "rounds": args.rounds,
        "warmup": args.warmup,
        "strategy": load_settings().search.strategy,
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "onnxruntime": onnxruntime.__version__,
        },
        "rows": rows,
    }
    out_dir = load_settings().paths.results
    (out_dir / f"{run_id}.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    dirty = " (dirty)" if git["dirty"] else ""
    lines = [
        f"# Latency run {run_id}",
        "",
        f"git {git['sha'][:7]}{dirty}; {result['machine']['platform']},"
        f" {result['machine']['cpu_count']} logical CPUs, Python"
        f" {result['machine']['python']}, onnxruntime"
        f" {result['machine']['onnxruntime']}; strategy {result['strategy']}.",
        "Cold = fresh process to first response (imports, chunks, model and"
        " embedding cache load, first request). Warm = in-process HTTP handling"
        f" (TestClient, no socket), {args.rounds} rounds of the dataset queries"
        f" after {args.warmup} discarded requests.",
        "",
        "| retriever | startup ms | first request ms | cold total ms |"
        " warm n | warm p50 ms | warm p95 ms | warm max ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['retriever']} | {r['startup_ms']:.0f} | {r['first_request_ms']:.1f}"
            f" | {r['cold_total_ms']:.0f} | {r['warm_n']} | {r['warm_p50_ms']:.2f}"
            f" | {r['warm_p95_ms']:.2f} | {r['warm_max_ms']:.2f} |"
        )
    (out_dir / f"{run_id}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {out_dir / run_id}.json")


if __name__ == "__main__":
    main()
