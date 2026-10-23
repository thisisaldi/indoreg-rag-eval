"""Vercel entrypoint (T-35, ADR-016): a module-level FastAPI `app`.

Vercel imports this file from the deployment root. Paths in the config are
relative, so the working directory is set to the repository root, and the model
files baked in by scripts/vercel_build.py are read offline.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))  # in case the package is not installed
os.chdir(ROOT)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from indoreg.api.app import create_app  # noqa: E402

app = create_app()
