# Search API image for local reproduction (BR6, T-26). The public deployment is
# Vercel (ADR-016). Model files and the embedding cache are baked in (ADR-008),
# so `docker run` needs no network and no mounts.
#
# Build after `make ingest` (the image takes data/chunks/, not the PDFs):
#   docker build -t indoreg-search .
#   docker run --rm -p 8000:8000 indoreg-search
# Another config file under configs/: --build-arg CONFIG=configs/<file>.yaml
# Another chunk directory (CI uses the fixture): --build-arg CHUNKS=<dir>

FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

FROM python:3.12.12-slim-bookworm AS build
ARG CONFIG=configs/default.yaml
ARG CHUNKS=data/chunks
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/app/hf INDOREG_CONFIG=$CONFIG
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev
COPY configs ./configs
COPY ${CHUNKS} ./data/chunks
# Build the configured serving index once: downloads the model (if any) at its
# pinned revision into HF_HOME and fills data/cache with chunk embeddings.
RUN .venv/bin/python -c "from indoreg.config import load_settings; \
from indoreg.api.app import build_index; build_index(load_settings())"

FROM python:3.12.12-slim-bookworm
ARG CONFIG=configs/default.yaml
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
USER app
ENV PATH=/app/.venv/bin:$PATH HF_HOME=/app/hf HF_HUB_OFFLINE=1 \
    PYTHONUNBUFFERED=1 INDOREG_CONFIG=$CONFIG
EXPOSE 8000
CMD ["uvicorn", "indoreg.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
