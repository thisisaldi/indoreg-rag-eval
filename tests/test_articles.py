"""Segmentation on synthetic OCR-like pages (no PDFs needed)."""

from indoreg.ingest.articles import clean_pages, readings, segment

HEADER = "PRESIDEN\nREPUBLIK INDONESIA\n"
PAGES = [
    HEADER + "-1-\nBAB I\nKETENTUAN UMUM\nPasal I\nIsi pasal satu.\n"
    "Pasal 2\nIsi pasal dua merujuk Pasal 1 ayat (1).\nPasal 3 . . .\nSK No 1 A",
    HEADER + "-2-\nPasal 3\nIsi pasal tiga.\nPasa74\nIsi pasal empat.\n"
    "5\nPasal\nIsi pasal lima.\nSK No 2 A",
    HEADER + "-3-\nPasal 6O\nIsi pasal enam puluh salah baca.\nPasal 6\n"
    "Isi pasal enam.\nPasal 7\nPenutup.\nDisahkan di Jakarta\nPENJELASAN\n"
    "Pasal 1\nCukup jelas.\nSK No 3 A",
]


def test_noise_filter_removes_only_stamps_catchwords_and_headers() -> None:
    texts = [ln.text for ln in clean_pages(PAGES)]
    for noise in (
        "SK No 1 A",
        "Pasal 3 . . .",
        "PRESIDEN",
        "REPUBLIK INDONESIA",
        "-2-",
    ):
        assert noise not in texts
    assert "BAB I" in texts and "Isi pasal tiga." in texts


def test_readings_include_confusable_digits_and_suffixes() -> None:
    assert (60, "", True, False) in readings("6O", None)
    assert (6, "O", True, False) in readings("6O", None)
    assert readings("12", None) == [(12, "", False, False)]
    assert readings("999", None) == []  # outside 1..300


def test_segment_sequence_with_ocr_errors_and_boundaries() -> None:
    seg = segment(PAGES, "doc")
    arts = [s.article for s in seg.spans]
    # "Pasal 6O" reads 60 or 6O-suffix; neither is the expected next (5 -> 6),
    # and the clean "Pasal 6" follows, so 6O stays unresolved instead of guessed.
    assert arts == ["1", "2", "3", "4", "5", "6", "7"]
    by = {s.article: s for s in seg.spans}
    assert by["1"].method == "confusion"  # "Pasal I"
    assert by["4"].method == "confusion"  # glued "Pasa74"
    assert by["5"].method == "confusion"  # number on the line before "Pasal"
    assert by["2"].method == "plain"
    assert seg.missing == [] and seg.unresolved == 1
    assert seg.boundary_page == 3 and seg.closing_page == 3


def test_spans_slice_the_cleaned_text_and_stop_before_closing() -> None:
    seg = segment(PAGES, "doc")
    by = {s.article: s for s in seg.spans}
    assert seg.text[by["2"].char_start :].startswith("Pasal 2\n")
    assert "Pasal 1 ayat (1)" in seg.text[by["2"].char_start : by["2"].char_end]
    assert seg.text[by["5"].char_start :].startswith("5\nPasal")
    last = seg.text[by["7"].char_start : by["7"].char_end]
    assert last.startswith("Pasal 7") and "Disahkan" not in last
    assert "Cukup jelas" not in seg.text[by["1"].char_start : by["7"].char_end]


def test_catchword_at_page_bottom_is_swapped_for_next_page_heading() -> None:
    # Page 1 ends with a clean catchword "Pasal 5"; the real heading opening page 2
    # is garbled ("Pasal S", S read as 5), so only the swap rule can place it.
    pages = [
        HEADER + "Pasal 1\nSatu.\nPasal 2\nDua.\nPasal 3\nTiga.\nPasal 4\nEmpat.\n"
        "Pasal 5\n...",
        HEADER + "Pasal S\nLima.\nPasal 6\nEnam.",
    ]
    seg = segment(pages, "doc")
    by = {s.article: s for s in seg.spans}
    assert [s.article for s in seg.spans] == ["1", "2", "3", "4", "5", "6"]
    assert by["5"].page == 2 and by["5"].method == "catchword_swap"


def test_clean_duplicate_on_next_page_wins_by_later_tiebreak() -> None:
    pages = [
        HEADER + "Pasal 1\nSatu.\nPasal 2\nDua.\nPasal 3\n...",
        HEADER + "Pasal3\nTiga.\nPasal 4\nEmpat.",
    ]
    by = {s.article: s for s in segment(pages, "doc").spans}
    assert by["3"].page == 2 and by["3"].method == "tiebreak_later"


def test_section_heading_ends_the_previous_article() -> None:
    pages = [
        "Pasal 1\nIsi pasal satu.\nBagian Kedua\nTransfer ke Luar Negeri\n"
        "Pasal 2\nIsi pasal dua.\nBAB II\nASAS\nPasal 3\nIsi pasal tiga.\n"
        "Paragraf I\nJudul\nPasal 4\nIsi pasal empat merujuk\nBAB I lagi.\n"
    ]
    seg = segment(pages, "doc")
    body = {s.article: seg.text[s.char_start : s.char_end] for s in seg.spans}
    assert body["1"] == "Pasal 1\nIsi pasal satu.\n"
    assert body["2"] == "Pasal 2\nIsi pasal dua.\n"
    assert body["3"] == "Pasal 3\nIsi pasal tiga.\n"
    assert "BAB I lagi." in body["4"]  # not a heading: text follows on the line
    assert [s.chapter for s in seg.spans] == [None, None, "BAB II", "BAB II"]


def test_clean_pages_fixes_ayat_digits_and_drops_garbled_letterhead() -> None:
    pages = [
        "REPI.JBLIK INDONESIA\n(l)\n(2lData Pribadi\nl2l Data lain\n"
        "dimaksud pada ayat (l) huruf a\nPasal 20 ayat (21 tetap\nisi\nisi\nisi\nisi"
    ]
    texts = [ln.text for ln in clean_pages(pages)]
    assert "REPI.JBLIK INDONESIA" not in texts
    assert texts[:4] == [
        "(1)",
        "(2) Data Pribadi",
        "(2) Data lain",
        "dimaksud pada ayat (1) huruf a",
    ]
    assert "Pasal 20 ayat (21 tetap" in texts  # ambiguous with ayat 21: untouched
