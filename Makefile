.PHONY: install lint typecheck test ingest search eval eval-drafts serve ingest-full eval-full

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

ingest:
	uv run python -m indoreg.ingest.pipeline

# Usage: make search Q="transfer data pribadi ke luar negeri"
search:
	uv run python -m indoreg.search "$(Q)"

eval:
	uv run python -m indoreg.eval.runner

# Big corpus (T-37, ADR-020): 11 GB external dump, pinned revision; local only.
# Search it with: INDOREG_CONFIG=configs/full.yaml make search Q="..."
EXTERNAL_DB_URL = https://huggingface.co/datasets/Azzindani/ID_REG_DB_2511/resolve/d53cafcef612b5ad563c6f36d2a237e8aad95a38/id_regulations.db

data/external/id_regulations.db:
	mkdir -p data/external
	curl -L -C - --retry 5 -o $@ $(EXTERNAL_DB_URL)

ingest-full: data/external/id_regulations.db
	uv run python -m indoreg.ingest.pipeline
	uv run python -m indoreg.ingest.external --config configs/full.yaml

eval-full:
	uv run python -m indoreg.eval.runner --config configs/full.yaml

# Unverified LLM drafts (ADR-014); results are marked UNVERIFIED and gitignored.
eval-drafts:
	uv run python -m indoreg.eval.runner --dataset eval/drafts/dataset_draft.jsonl --allow-drafts

# Serves search.retriever from configs/default.yaml; docs at http://127.0.0.1:8000/docs
serve:
	uv run uvicorn indoreg.api.app:create_app --factory
