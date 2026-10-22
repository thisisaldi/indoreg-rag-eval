.PHONY: install lint typecheck test ingest search eval eval-drafts serve

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

# Unverified LLM drafts (ADR-014); results are marked UNVERIFIED and gitignored.
eval-drafts:
	uv run python -m indoreg.eval.runner --dataset eval/drafts/dataset_draft.jsonl --allow-drafts

serve:
	@echo "not yet: API arrives in T-24"; exit 1
