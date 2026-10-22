.PHONY: install lint typecheck test ingest eval serve

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
	@echo "not yet: ingestion arrives in T-06/T-07"; exit 1

eval:
	@echo "not yet: eval runner arrives in T-14"; exit 1

serve:
	@echo "not yet: API arrives in T-24"; exit 1
