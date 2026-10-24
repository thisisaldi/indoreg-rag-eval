from pathlib import Path

from indoreg.config import ExternalCorpusConfig
from indoreg.ingest.external import to_chunks

CFG = ExternalCorpusConfig(
    db=Path("x.db"),
    sha256="0",
    source_url="https://example.org/ds",
    base_chunks=Path("a.jsonl"),
    min_chars=10,
    types={"UNDANG-UNDANG": "uu", "PERATURAN PEMERINTAH": "pp"},
)
LONG = "Setiap orang wajib menjaga data."


def test_filters_dedupes_and_cites() -> None:
    rows = [
        ("UNDANG-UNDANG", "11", 2008, "ITE", "N/A", "Pasal 26", LONG),  # in manifest
        ("UNDANG-UNDANG", "5", 2010, "A", "BAB I", "Pasal 1", LONG),
        ("UNDANG-UNDANG", "5", 2010, "A", "N/A", "Pasal 1", LONG),  # repeated article
        (
            "UNDANG-UNDANG",
            "5",
            2010,
            "A",
            "N/A",
            "Pembukaan",
            LONG,
        ),  # not a body article
        ("UNDANG-UNDANG", "5", 2010, "A", "N/A", "Pasal 2", "pendek"),  # too short
        ("PERATURAN BUPATI", "1", 2010, "R", "N/A", "Pasal 1", LONG),  # not national
        (
            "UNDANG-UNDANG",
            "5",
            2010,
            "B",
            "N/A",
            "Pasal 3A",
            LONG,
        ),  # same id, other title
    ]
    out = list(to_chunks(rows, CFG, {"uu-11-2008"}))
    assert [c.chunk_id for c in out] == [
        "ext-uu-5-2010:article:1",
        "ext-uu-5-2010:article:1#2",
        out[2].chunk_id,
    ]
    assert out[2].doc_id.startswith("ext-uu-5-2010-") and out[2].article == "3A"
    first = out[0]
    assert first.text == f"Pasal 1\n{LONG}" and first.char_end == len(first.text)
    assert first.chapter == "BAB I" and out[1].chapter is None
    assert first.doc_status == "unknown" and first.source_url == CFG.source_url
    assert first.title == "Undang-Undang Nomor 5 Tahun 2010 tentang A"
