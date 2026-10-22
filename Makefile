.PHONY: install lint typecheck test ingest search eval serve

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
	@echo "not yet: eval runner arrives in T-14"; exit 1

serve:
	@echo "not yet: API arrives in T-24"; exit 1
