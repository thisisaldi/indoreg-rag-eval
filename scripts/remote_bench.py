"""Latency of a deployed API from this machine (T-35). Stdlib only.

Sends the dataset queries `--rounds` times to <url>/search and records the
client round trip (network included) and the server's own `latency_ms`
(retrieval only). The first request of the run is reported separately; it may
or may not hit a cold instance, which this script cannot control. Also checks
that a CORS preflight from `--origin` is allowed.

Usage:
  uv run python scripts/remote_bench.py https://indoreg-rag-eval.vercel.app
Writes reports/results/<timestamp>-<sha>-remote.{json,md}.
"""

import argparse
import json
import time
import urllib.request
from datetime import UTC, datetime

from indoreg.config import load_settings
from indoreg.eval.dataset import load_dataset
from indoreg.eval.runner import git_state, percentile


def call(req: urllib.request.Request) -> tuple[float, int, dict[str, str], bytes]:
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return (time.perf_counter() - t) * 1000, r.status, dict(r.headers), body


def search(url: str, query: str) -> tuple[float, dict[str, str], dict]:
    data = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/search", data=data, headers={"Content-Type": "application/json"}
    )
    ms, status, headers, body = call(req)
    if status != 200:
        raise SystemExit(f"/search returned {status}")
    return ms, headers, json.loads(body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--origin", default="https://naufaldi.vercel.app")
    args = ap.parse_args()
    url = args.url.rstrip("/")
    settings = load_settings()
    queries = [q.query for q in load_dataset(settings.paths.dataset)]

    first_ms, headers, first = search(url, queries[0])
    rtt: list[float] = []
    server: list[float] = []
    for i in range(args.rounds * len(queries)):
        ms, _, body = search(url, queries[i % len(queries)])
        rtt.append(ms)
        server.append(body["latency_ms"])

    pre = urllib.request.Request(
        f"{url}/search",
        method="OPTIONS",
        headers={
            "Origin": args.origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    _, pre_status, pre_headers, _ = call(pre)
    allowed = {k.lower(): v for k, v in pre_headers.items()}.get(
        "access-control-allow-origin"
    )

    git = git_state()
    now = datetime.now(UTC)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + f"-{git['sha'][:7]}-remote"
    row = {
        "url": url,
        "retriever": first["retriever"],
        "vercel_id": {k.lower(): v for k, v in headers.items()}.get("x-vercel-id"),
        "first_request_ms": first_ms,
        "n": len(rtt),
        "rtt_p50_ms": percentile(rtt, 50),
        "rtt_p95_ms": percentile(rtt, 95),
        "server_p50_ms": percentile(server, 50),
        "server_p95_ms": percentile(server, 95),
        "cors_preflight_status": pre_status,
        "cors_allow_origin": allowed,
    }
    result = {
        "run_id": run_id,
        "timestamp": now.isoformat(),
        "git": git,
        "method": __doc__,
        "rounds": args.rounds,
        "origin": args.origin,
        "row": row,
    }
    out = settings.paths.results
    (out / f"{run_id}.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    md = [
        f"# Remote latency {run_id}",
        "",
        f"{url} (x-vercel-id {row['vercel_id']}), retriever {row['retriever']},"
        f" {row['n']} requests after one first request. Round trip includes the"
        " network from the measuring machine; server time is the API's"
        " `latency_ms` (retrieval only).",
        "",
        "| first request ms | round trip p50 | round trip p95 | server p50 |"
        " server p95 | CORS preflight |",
        "|---|---|---|---|---|---|",
        f"| {first_ms:.0f} | {row['rtt_p50_ms']:.0f} | {row['rtt_p95_ms']:.0f} |"
        f" {row['server_p50_ms']:.1f} | {row['server_p95_ms']:.1f} |"
        f" {pre_status}, allow-origin {allowed} |",
    ]
    (out / f"{run_id}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
