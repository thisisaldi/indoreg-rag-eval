"""Check data/manifest.json: required fields, allowed values, file hashes.

Usage: python scripts/check_manifest.py [--strict]
Exit 1 on a missing key, bad value, missing file or hash mismatch.
Null fields are reported as incomplete; --strict also fails on them (T-03 acceptance).
Stdlib only; replaced by a proper module and tests in T-05/T-06.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
RAW = ROOT / "data" / "raw"
REQUIRED = [
    "doc_id",
    "title",
    "reg_type",
    "number",
    "year",
    "status",
    "status_source",
    "source_url",
    "retrieved_on",
    "filename",
    "sha256",
    "text_quality",
]
STATUS = {"in_force", "amended", "revoked", "unknown"}
TEXT_QUALITY = {"native", "image_text_layer"}


def main() -> int:
    strict = "--strict" in sys.argv
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors, incomplete = [], []
    ids = [e.get("doc_id") for e in entries]
    if len(ids) != len(set(ids)):
        errors.append("duplicate doc_id")
    for e in entries:
        did = e.get("doc_id", "?")
        for k in REQUIRED:
            if k not in e:
                errors.append(f"{did}: missing key {k}")
            elif e[k] is None:
                incomplete.append(f"{did}: {k}")
        if e.get("status") is not None and e["status"] not in STATUS:
            errors.append(f"{did}: bad status {e['status']!r}")
        if e.get("text_quality") not in TEXT_QUALITY:
            errors.append(f"{did}: bad text_quality {e.get('text_quality')!r}")
        path = RAW / e.get("filename", "")
        if not path.is_file():
            errors.append(f"{did}: file not found {path.name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != e.get("sha256"):
            errors.append(f"{did}: sha256 mismatch")
    print(
        f"{len(entries)} entries, {len(errors)} errors, "
        f"{len(incomplete)} incomplete fields"
    )
    for x in errors:
        print("ERROR", x)
    for x in incomplete:
        print("INCOMPLETE", x)
    return 1 if errors or (strict and incomplete) else 0


if __name__ == "__main__":
    sys.exit(main())
