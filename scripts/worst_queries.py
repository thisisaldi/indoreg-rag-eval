"""List the worst queries of one run in a result file, for error analysis (T-21).

For each query, worst nDCG@10 first: the query text, labelled articles with
grade, the run's top 10, and the rank of each labelled article in every other
run named with --compare (for example the members of a hybrid). Metrics are
read from the result file, not recomputed; the summary adds counts over the
processed corpus (section headings inside article spans, token lengths).

Usage:
  uv run python scripts/worst_queries.py reports/results/<run>.json \
      --run hybrid/article --compare bm25-id-title/article dense-e5-small/article
"""

import argparse
import json
import re
from pathlib import Path

# A section heading inside an article span belongs to the next article.
HEADING = re.compile(r"\n\s*(BAB\s+[IVXLCDM]+|Bagian\s+Ke[a-z]+|Paragraf\s+\d+)\b")


def rank_of(unit: str, ranking: list[str]) -> str:
    return str(ranking.index(unit) + 1) if unit in ranking else "-"


def article_texts(processed: Path) -> dict[str, str]:
    out = {}
    for spans_file in sorted(processed.glob("*.articles.json")):
        doc = spans_file.name.removesuffix(".articles.json")
        text = (processed / f"{doc}.txt").read_text(encoding="utf-8")
        for s in json.loads(spans_file.read_text(encoding="utf-8")):
            out[f"{doc}:{s['article']}"] = text[s["char_start"] : s["char_end"]]
    return out


def summary(rows: list[dict], tokenizer: str | None) -> None:
    """Labelled units missed in the top 10, by document and query type."""
    by_doc: dict[str, list[int]] = {}
    by_type: dict[str, list[float]] = {}
    labelled: dict[str, bool] = {}
    for q in rows:
        by_type.setdefault(q["type"], []).append(q["ndcg@10"])
        for unit in q["relevant"]:
            hit = unit in q["ranking"][:10]
            by_doc.setdefault(unit.split(":")[0], []).append(int(hit))
            labelled[unit] = labelled.get(unit, False) or hit
    texts = article_texts(Path("data/processed"))
    trailing = [u for u, t in texts.items() if HEADING.search(t)]
    print("# Summary\n")
    print(
        f"articles whose span contains a section heading: {len(trailing)}"
        f" of {len(texts)}"
    )
    print("labelled (query, article) pairs found in top 10, by document:")
    for doc, hits in sorted(by_doc.items()):
        print(f"  {doc}: {sum(hits)}/{len(hits)}")
    print("mean nDCG@10 by query type:")
    for t, vals in sorted(by_type.items()):
        print(f"  {t}: {sum(vals) / len(vals):.3f} (n={len(vals)})")
    if tokenizer:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        repo, _, rev = tokenizer.partition("@")
        path = hf_hub_download(repo, "tokenizer.json", revision=rev or None)
        tok = Tokenizer.from_file(path)
        long = {
            u: n
            for u in labelled
            if (n := len(tok.encode("passage: " + texts[u]).ids)) > 512
        }
        print(f"labelled articles over 512 tokens ({tokenizer}): {len(long)}")
        for u, n in sorted(long.items()):
            print(f"  {u}: {n} tokens, found in some top 10: {labelled[u]}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("result", type=Path)
    ap.add_argument("--run", required=True)
    ap.add_argument("--compare", nargs="*", default=[])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--dataset", type=Path, default=Path("eval/dataset.jsonl"))
    ap.add_argument("-n", type=int, default=15)
    ap.add_argument(
        "--tokenizer",
        default=None,
        help="<repo id>@<revision>; adds token counts of long labelled articles",
    )
    args = ap.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    by_run = result["results"][args.split]
    texts = {
        q["query_id"]: q["query"]
        for q in map(json.loads, args.dataset.read_text(encoding="utf-8").splitlines())
    }
    others = {
        name: {q["query_id"]: q["ranking"] for q in by_run[name]["queries"]}
        for name in args.compare
    }
    rows = sorted(
        by_run[args.run]["queries"], key=lambda q: (q["ndcg@10"], q["query_id"])
    )
    summary(rows, args.tokenizer)
    header = " | ".join(["rank in " + args.run, *args.compare])
    for q in rows[: args.n]:
        qid = q["query_id"]
        print(f"## {qid} ({q['type']}) ndcg@10={q['ndcg@10']:.3f} rr={q['rr']:.3f}")
        print(f"query: {texts[qid]}")
        print(f"top10: {', '.join(q['ranking'][:10])}")
        print(f"labelled (grade): {header}")
        for unit, grade in sorted(q["relevant"].items()):
            ranks = [rank_of(unit, q["ranking"])]
            ranks += [rank_of(unit, others[name][qid]) for name in args.compare]
            print(f"  {unit} ({grade}): {' | '.join(ranks)}")
        print()


if __name__ == "__main__":
    main()
