"""Run the configured retrievers on the labeled queries and write the results.

Run: python -m indoreg.eval.runner [--config PATH] [--dataset PATH] [--allow-drafts]
Writes reports/results/<run_id>.json (config, git SHA, timestamp, per-query rows,
aggregates, latency) and <run_id>.md (comparison table). Metrics are
deterministic; only timestamp and latency change between reruns.
"""

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from indoreg.config import Settings, load_settings
from indoreg.eval.dataset import DatasetError, Query, load_dataset
from indoreg.eval.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from indoreg.logging import configure_logging, get_logger
from indoreg.retrieval.base import Retriever
from indoreg.retrieval.registry import build_retriever
from indoreg.schemas import Chunk
from indoreg.search import load_chunks

log = get_logger(__name__)
NOT_VERIFIED = "not human-verified"  # source_note marker (ADR-015)


def chunk_unit(chunk: Chunk) -> str | None:
    """Article unit of a chunk (design.md 4.1); article chunks map one to one."""
    return f"{chunk.doc_id}:{chunk.article}" if chunk.article else None


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def evaluate(
    retriever: Retriever,
    chunks: Sequence[Chunk],
    queries: Sequence[Query],
    recall_ks: Sequence[int],
    ndcg_k: int,
    depth: int,
) -> list[dict[str, Any]]:
    unit_of = {c.chunk_id: chunk_unit(c) for c in chunks}
    rows = []
    for q in queries:
        t0 = time.perf_counter()
        hits = retriever.search(q.query, depth)
        latency_ms = (time.perf_counter() - t0) * 1000
        ranking = [u for h in hits if (u := unit_of[h.chunk_id]) is not None]
        rows.append(
            {
                "query_id": q.query_id,
                "type": q.type,
                "ranking": ranking[: max(*recall_ks, ndcg_k)],
                "relevant": q.qrels,
                **{f"recall@{k}": recall_at_k(ranking, q.qrels, k) for k in recall_ks},
                "rr": reciprocal_rank(ranking, q.qrels),
                f"ndcg@{ndcg_k}": ndcg_at_k(ranking, q.qrels, ndcg_k),
                "latency_ms": latency_ms,
            }
        )
    return rows


def summarize(
    rows: Sequence[dict[str, Any]], metric_keys: Sequence[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(rows)}
    for key in metric_keys:
        out[key] = mean(r[key] for r in rows) if rows else None
    lat = [r["latency_ms"] for r in rows]
    out["latency_p50_ms"] = percentile(lat, 50) if lat else None
    out["latency_p95_ms"] = percentile(lat, 95) if lat else None
    return out


def git_state() -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError) as e:
        log.warning("git state unavailable", extra={"fields": {"error": str(e)}})
        return {"sha": "unknown", "dirty": None}
    return {"sha": sha, "dirty": dirty}


def _fmt(value: float | None, digits: int) -> str:
    """n/a for a split with no queries (e.g. before the test split exists)."""
    return "n/a" if value is None else f"{value:.{digits}f}"


def markdown(result: dict[str, Any]) -> str:
    keys = result["metric_keys"]
    head = [
        "retriever",
        "n",
        *[{"rr": "MRR"}.get(k, k) for k in keys],
        "p50 ms",
        "p95 ms",
    ]
    lines = [f"# Eval run {result['run_id']}", ""]
    if result["dataset"]["unverified_drafts"]:
        lines += [
            "> **UNVERIFIED LABELS.** These numbers use LLM-drafted labels that have",
            "> not been verified yet (ADR-014). Do not cite them.",
            "",
        ]
    elif not result["dataset"]["labels_human_verified"]:
        lines += [
            "> Labels were drafted and checked by an LLM,"
            " not human-verified (ADR-015).",
            "",
        ]
    ds, git = result["dataset"], result["git"]
    dirty = " (dirty)" if git["dirty"] else ""
    lines += [
        f"Dataset `{ds['path']}` (sha256 {ds['sha256'][:12]}),"
        f" git {git['sha'][:7]}{dirty}.",
        "Bootstrap confidence intervals arrive with T-19; without them, do not call a"
        " difference between retrievers real.",
        "",
    ]
    for split, by_ret in result["results"].items():
        lines += [f"## {split}", "", "| " + " | ".join(head) + " |"]
        lines.append("|" + "---|" * len(head))
        for name, res in by_ret.items():
            s = res["summary"]
            cells = [name, str(s["n"]), *[_fmt(s[k], 3) for k in keys]]
            cells += [_fmt(s["latency_p50_ms"], 2), _fmt(s["latency_p95_ms"], 2)]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def run(settings: Settings, dataset_path: Path, allow_drafts: bool) -> dict[str, Any]:
    cfg = settings.eval
    queries = load_dataset(dataset_path, allow_drafts)
    drafts = any(q.draft_status is not None for q in queries)
    human_verified = not any(NOT_VERIFIED in q.source_note for q in queries)
    chunks = load_chunks(settings)
    metric_keys = [*[f"recall@{k}" for k in cfg.recall_ks], "rr", f"ndcg@{cfg.ndcg_k}"]
    results: dict[str, dict[str, Any]] = {}
    for split in cfg.splits:
        split_q = [q for q in queries if q.split == split]
        results[split] = {}
        for name in cfg.retrievers:
            retriever = build_retriever(name, settings)
            retriever.build(chunks)
            rows = evaluate(
                retriever, chunks, split_q, cfg.recall_ks, cfg.ndcg_k, cfg.depth
            )
            results[split][name] = {
                "summary": summarize(rows, metric_keys),
                "queries": rows,
            }
    now = datetime.now(UTC)
    git = git_state()
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + f"-{git['sha'][:7]}"
    if drafts:
        run_id += "-unverified"
    return {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "git": git,
        "config": settings.model_dump(mode="json"),
        "dataset": {
            "path": dataset_path.as_posix(),
            "sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
            "queries": len(queries),
            "unverified_drafts": drafts,
            "labels_human_verified": human_verified,
        },
        "chunks": len(chunks),
        "metric_keys": metric_keys,
        "results": results,
    }


def write(result: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['run_id']}.json"
    path.write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / f"{result['run_id']}.md").write_text(markdown(result), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument(
        "--allow-drafts",
        action="store_true",
        help="accept unverified LLM drafts; results are marked UNVERIFIED",
    )
    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    configure_logging(settings.logging.level)
    try:
        result = run(
            settings, args.dataset or settings.paths.dataset, args.allow_drafts
        )
    except (DatasetError, FileNotFoundError) as e:
        sys.stderr.write(f"{e}\n")
        return 1
    path = write(result, settings.paths.results)
    sys.stdout.write(markdown(result) + f"\nWritten: {path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
