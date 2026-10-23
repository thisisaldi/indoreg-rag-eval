"""Vercel build step (T-35): bake the serving index into the deployment.

Runs after dependencies are installed. Builds the configured serving retriever
once, which downloads its model files at the pinned revision into
`paths.models` and writes the chunk embeddings to `paths.cache`, so the
function starts without network access. Also prints the size of what it wrote.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)  # config paths are relative to the repository root

from indoreg.api.app import build_index  # noqa: E402
from indoreg.config import load_settings  # noqa: E402


def size_mb(path: Path) -> float:
    files = path.rglob("*") if path.is_dir() else []
    return sum(f.stat().st_size for f in files if f.is_file()) / 1e6


def main() -> None:
    settings = load_settings(Path("configs/default.yaml"))
    index = build_index(settings)
    for name in ("models", "cache", "chunks"):
        path = ROOT / getattr(settings.paths, name)
        print(f"{name}: {path} {size_mb(path):.1f} MB")
    print(f"served retriever: {index.retriever.name}, chunks: {len(index.chunks)}")


if __name__ == "__main__":
    main()
