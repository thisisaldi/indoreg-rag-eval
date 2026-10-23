#!/usr/bin/env bash
# Build the image from the fixture corpus and smoke-test it (T-28): /health
# answers with the expected index, /search returns cited results, the process
# is not root. Used by CI; runs locally with Docker too.
set -euo pipefail

IMAGE=indoreg-ci
NAME=indoreg-smoke
PORT=${PORT:-8000}

docker build -t "$IMAGE" \
  --build-arg CONFIG=configs/ci-image.yaml \
  --build-arg CHUNKS=tests/fixtures/ci_eval/chunks .

docker rm -f "$NAME" >/dev/null 2>&1 || true
trap 'docker logs "$NAME" 2>&1 | tail -20; docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$NAME" -p "$PORT:8000" "$IMAGE" >/dev/null

health=""
for _ in $(seq 1 30); do
  if health=$(curl -fsS "http://127.0.0.1:$PORT/health"); then break; fi
  sleep 1
done
echo "health: $health"
python3 - "$health" <<'EOF'
import json, sys
h = json.loads(sys.argv[1])
assert h["status"] == "ok" and h["retriever"] == "bm25-basic", h
assert h["chunks"] == 12, h  # tests/fixtures/ci_eval/chunks/article.jsonl
EOF

search=$(curl -fsS -X POST "http://127.0.0.1:$PORT/search" \
  -H "Content-Type: application/json" -d '{"query": "data pelanggan", "top_k": 3}')
python3 - "$search" <<'EOF'
import json, sys
s = json.loads(sys.argv[1])
assert len(s["results"]) == 3 and s["disclaimer"], s
assert s["results"][0]["doc_id"].startswith("fx-"), s
EOF

user=$(docker exec "$NAME" whoami)
test "$user" != root
echo "smoke test passed (user $user)"
