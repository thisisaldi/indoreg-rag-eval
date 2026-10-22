"""OCR-tolerant article segmentation (ADR-010).

Port of the scratch/segment_v2.py spike. Steps: noise filter, fuzzy "Pasal N"
candidates, sequence decoding, catchword swap, gap fill, Penjelasan boundary
(ADR-012), closing line. Unresolved markers stay unresolved; nothing is guessed.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import NamedTuple

from indoreg.schemas import ArticleSpan, Method

# Characters the OCR layer substitutes for digits.
CONF = {"O": "0", "l": "1", "I": "1", "T": "7", "S": "5", "B": "8"}
STAMP = re.compile(r"^\s*SK\s*No")
CATCH = re.compile(r"\.\s\.(?:\s\.)?\s*$")
PAGENUM = re.compile(r"[-–—]\s*[0-9OlI]{1,3}\s*[-–—]")
TOKEN = re.compile(r"([0-9OlITSB](?: ?[0-9OlITSB]){0,3})([A-Z])?(?![A-Za-z0-9])")
PURE_NUM = re.compile(r"^([0-9OlITSB](?: ?[0-9OlITSB]){0,3})([A-Z])?$")
PENJ = re.compile(r"PENJE.{0,3}ASAN")
PDP = re.compile(r"(?i)PASAL\s*DEMI\s*PASAL")
MAX_ARTICLE = 300
HEADER_ZONE, FOOTER_ZONE = 6, 3  # lines checked for repeated headers/footers
CATCHWORD_ZONE = 3  # last lines of a page where catchwords sit
NEXT_PAGE_HEAD = 6  # first lines of the next page searched for the real heading

Reading = tuple[int, str, bool, bool]  # number, suffix, substituted, inner space
Key = tuple[int, str]


class Line(NamedTuple):
    page: int
    text: str


@dataclass
class Candidate:
    idx: int  # line index of the word "Pasal"
    start_idx: int  # first line of the marker (number line if it comes first)
    page: int
    raw: str
    kind: str  # inline | next-line | prev-line
    heading: bool
    readings: list[Reading]
    context: str
    glued_keys: set[Key] = field(default_factory=set)


@dataclass
class Accepted:
    cand: Candidate
    key: Key
    how: str  # clean | confusion | catchword_swap | gap_fill


@dataclass
class Segmentation:
    text: str
    spans: list[ArticleSpan]
    pages_in_text: list[int]  # page of each cleaned line
    boundary_page: int | None
    closing_page: int | None
    last_article: int
    missing: list[int]
    unresolved: int
    methods: Counter[str]


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def clean_pages(pages: list[str]) -> list[Line]:
    """Drop stamps, page-bottom catchwords and repeated header/footer lines only."""
    plines = [[ln.strip() for ln in t.splitlines() if ln.strip()] for t in pages]

    def zone(i: int, k: int) -> bool:
        return k < HEADER_ZONE or k >= len(plines[i]) - FOOTER_ZONE

    def key(ln: str) -> str:
        return "<PAGENUM>" if PAGENUM.fullmatch(ln) else ln

    seen: Counter[str] = Counter()
    for i, ls in enumerate(plines):
        seen.update(
            {
                key(ln)
                for k, ln in enumerate(ls)
                if zone(i, k) and not STAMP.match(ln) and not CATCH.search(ln)
            }
        )
    repeated = {k for k, c in seen.items() if c > len(pages) / 2}
    out: list[Line] = []
    for i, ls in enumerate(plines):
        for k, ln in enumerate(ls):
            noise = STAMP.match(ln) or CATCH.search(ln)
            if noise or (zone(i, k) and key(ln) in repeated):
                continue
            out.append(Line(i + 1, ln))
    return out


def readings(token: str, suffix: str | None) -> list[Reading]:
    chars = [c for c in token if c != " "]
    inner = " " in token
    digits = "".join(CONF.get(c, c) for c in chars)
    subst = any(not c.isdigit() for c in chars) or bool(suffix and suffix in CONF)
    out: set[Reading] = set()
    if digits.isdigit() and 0 < int(digits) <= MAX_ARTICLE:
        out.add((int(digits), suffix or "", subst, inner))
    if suffix is None and len(chars) >= 2 and chars[-1] in CONF:
        d2 = "".join(CONF.get(c, c) for c in chars[:-1])
        if d2.isdigit() and 0 < int(d2) <= MAX_ARTICLE:
            out.add((int(d2), chars[-1], True, inner))
    return sorted(out)


def _word_match(run: str) -> int | None:
    """Length (4 to 6) of the prefix closest to 'Pasal', if within edit distance 2."""
    best: tuple[int, int] | None = None
    for k in range(4, min(len(run), 6) + 1):
        word = run[:k]
        if word[0] in "Pp":
            d = lev(word.lower(), "pasal")
            if d <= 2 and (best is None or d < best[0]):
                best = (d, k)
    return best[1] if best else None


def find_candidates(lines: list[Line]) -> list[Candidate]:
    cands: list[Candidate] = []
    for idx, (pg, line) in enumerate(lines):
        for m in re.finditer(r"[A-Za-z]{3,7}", line):
            s = m.start()
            if s > 0 and line[s - 1].isalnum():
                continue
            k = _word_match(m.group())
            if k is None:
                continue
            rest = line[s + k :]
            rest_s = rest.lstrip(" \t")
            at_start = line[:s].strip(" .\t") == ""
            t = TOKEN.match(rest_s)
            split_rd = readings(t.group(1), t.group(2)) if t else []
            glued_rd: list[Reading] = []
            tg = None
            # Glued form: the word's "l" read as 7, 1 or |, e.g. "Pasa722" = Pasal 22.
            glued = rest_s[:1] in ("7", "1", "|")
            if k == 4 and lev(m.group()[:4].lower(), "pasa") <= 1 and glued:
                rest_g = rest_s[1:].lstrip(" \t")
                tg = TOKEN.match(rest_g)
                if tg:
                    glued_rd = [
                        (n, sf, True, inn)
                        for n, sf, _, inn in readings(tg.group(1), tg.group(2))
                    ]
            if t or tg:
                tok = t or tg
                assert tok is not None
                trailing = (rest_s if t else rest_g)[tok.end() :]
                cands.append(
                    Candidate(
                        idx=idx,
                        start_idx=idx,
                        page=pg,
                        raw=line[s:].rstrip(),
                        kind="inline",
                        heading=at_start and trailing.strip(" .,;:-") == "",
                        readings=sorted(set(split_rd + glued_rd)),
                        context=line,
                        glued_keys={(n, sf) for n, sf, _, _ in glued_rd},
                    )
                )
            elif at_start and rest_s.strip(" .") == "":
                cands.extend(_two_line_candidate(lines, idx, pg, line))
    return cands


def _two_line_candidate(
    lines: list[Line], idx: int, pg: int, line: str
) -> list[Candidate]:
    """A bare 'Pasal' line takes its number from the next line, else the previous."""
    nxt = lines[idx + 1].text if idx + 1 < len(lines) else ""
    prv = lines[idx - 1].text if idx > 0 else ""
    for num_line, kind, start in ((nxt, "next-line", idx), (prv, "prev-line", idx - 1)):
        t = PURE_NUM.match(num_line)
        if t:
            rd = readings(t.group(1), t.group(2))
            if rd:
                raw = f"{line} / {nxt}" if kind == "next-line" else f"{prv} / {line}"
                return [Candidate(idx, start, pg, raw, kind, True, rd, raw)]
            return []
    return []


def _clean_key(c: Candidate) -> Key | None:
    if c.glued_keys:  # garbled word: the digit boundary itself is uncertain
        return None
    clean = [r for r in c.readings if not r[2] and not r[3]]
    return (clean[0][0], clean[0][1]) if clean else None


def decode(heads: list[Candidate]) -> tuple[list[Accepted], list[Candidate]]:
    """Phase A: clean digits, longest increasing subsequence (later wins ties).
    Phase B: other readings only if they equal the expected next article."""
    anchors = [(i, k) for i, c in enumerate(heads) if (k := _clean_key(c))]
    dp: list[tuple[int, int]] = []
    for a, (_, ka) in enumerate(anchors):
        best = (1, -1)
        for b in range(a):
            if anchors[b][1] < ka and dp[b][0] + 1 >= best[0]:
                best = (dp[b][0] + 1, b)
        dp.append(best)
    keep: set[int] = set()
    if anchors:
        end = max(range(len(anchors)), key=lambda a: (dp[a][0], a))
        while end != -1:
            keep.add(anchors[end][0])
            end = dp[end][1]
    keys = dict(anchors)
    accepted: list[Accepted] = []
    unresolved: list[Candidate] = []
    last: Key = (0, "")
    for i, c in enumerate(heads):
        if i in keys:
            if i in keep:
                accepted.append(Accepted(c, keys[i], "clean"))
                last = keys[i]
            else:
                unresolved.append(c)
            continue
        next_suffix = "A" if last[1] == "" else chr(ord(last[1]) + 1)
        expected = {(last[0] + 1, ""), (last[0], next_suffix)}
        nxt = next((keys[j] for j in sorted(keep) if j > i), None)
        hit = next(
            (
                (r[0], r[1])
                for r in c.readings
                if (r[0], r[1]) in expected and (nxt is None or (r[0], r[1]) < nxt)
            ),
            None,
        )
        if hit:
            accepted.append(Accepted(c, hit, "confusion"))
            last = hit
        else:
            unresolved.append(c)
    return accepted, unresolved


def swap_catchwords(
    accepted: list[Accepted], unresolved: list[Candidate], lines: list[Line]
) -> None:
    """Replace a marker in a page's last lines (a catchword) by the same article's
    heading in the next page's first lines."""
    per_page = Counter(ln.page for ln in lines)
    pos: list[int] = []
    count: Counter[int] = Counter()
    for ln in lines:
        count[ln.page] += 1
        pos.append(count[ln.page])
    for ai, a in enumerate(accepted):
        if per_page[a.cand.page] - pos[a.cand.idx] >= CATCHWORD_ZONE:
            continue
        for ui, u in enumerate(unresolved):
            same = any((r[0], r[1]) == a.key for r in u.readings)
            if u.page == a.cand.page + 1 and pos[u.idx] <= NEXT_PAGE_HEAD and same:
                accepted[ai] = Accepted(u, a.key, "catchword_swap")
                unresolved[ui] = a.cand
                break


def gap_fill(
    accepted: list[Accepted], unresolved: list[Candidate]
) -> tuple[list[Accepted], list[Candidate]]:
    """Accept the only unresolved heading between neighbours N-1 and N+1 as N."""
    out = accepted[:1]
    for a, b in zip(accepted, accepted[1:], strict=False):
        if a.key[1] == "" and b.key[1] == "" and b.key[0] - a.key[0] == 2:
            pool = [u for u in unresolved if a.cand.idx < u.idx < b.cand.idx]
            if len(pool) == 1:
                out.append(Accepted(pool[0], (a.key[0] + 1, ""), "gap_fill"))
                unresolved = [u for u in unresolved if u is not pool[0]]
        out.append(b)
    return out, unresolved


def closing_index(texts: list[str], end: int, after: int) -> int | None:
    """First line after the last article starting like 'Ditetapkan di'/'Disahkan di'."""
    for i in range(after + 1, end):
        words = texts[i].split()
        if len(words) >= 2:
            head = " ".join(words[:2]).lower()
            if min(lev(head, "ditetapkan di"), lev(head, "disahkan di")) <= 2:
                return i
    return None


def _method(a: Accepted, unresolved: list[Candidate]) -> Method:
    if a.how == "gap_fill":
        return "gap_fill"
    if a.how == "catchword_swap":
        return "catchword_swap"
    if any(
        u.idx < a.cand.idx and any((r[0], r[1]) == a.key for r in u.readings)
        for u in unresolved
    ):
        return "tiebreak_later"
    raw = a.cand.context if a.cand.kind == "inline" else a.cand.raw
    m = re.fullmatch(r"Pasal (\d+)", raw)
    exact = m is not None and int(m.group(1)) == a.key[0] and a.key[1] == ""
    return "plain" if exact else "confusion"


def segment(pages: list[str], doc_id: str) -> Segmentation:
    lines = clean_pages(pages)
    texts = [ln.text for ln in lines]
    offsets: list[int] = []
    o = 0
    for t in texts:
        offsets.append(o)
        o += len(t) + 1
    text = "\n".join(texts)
    cands = find_candidates(lines)
    bound = next(
        (i for i, t in enumerate(texts) if len(t) < 90 and PENJ.search(t)), None
    )
    if bound is None:
        bound = next(
            (i for i, t in enumerate(texts) if len(t) < 90 and PDP.search(t)), None
        )
    end = bound if bound is not None else len(lines)
    heads = [c for c in cands if c.idx < end and c.heading]
    accepted, unresolved = decode(heads)
    swap_catchwords(accepted, unresolved, lines)
    accepted, unresolved = gap_fill(accepted, unresolved)
    last_start = accepted[-1].cand.start_idx if accepted else 0
    close = closing_index(texts, end, last_start)
    spans: list[ArticleSpan] = []
    methods: Counter[str] = Counter()
    for j, a in enumerate(accepted):
        s_line = a.cand.start_idx
        if j + 1 < len(accepted):
            e_line = accepted[j + 1].cand.start_idx
        else:
            e_line = close if close is not None else end
        method = _method(a, unresolved)
        methods[method] += 1
        spans.append(
            ArticleSpan(
                doc_id=doc_id,
                article=f"{a.key[0]}{a.key[1]}",
                page=lines[s_line].page,
                char_start=offsets[s_line],
                char_end=offsets[e_line] if e_line < len(offsets) else len(text),
                method=method,
                marker_raw=a.cand.raw,
            )
        )
    last = max((a.key[0] for a in accepted), default=0)
    plain = {a.key[0] for a in accepted if a.key[1] == ""}
    return Segmentation(
        text=text,
        spans=spans,
        pages_in_text=[ln.page for ln in lines],
        boundary_page=lines[bound].page if bound is not None else None,
        closing_page=lines[close].page if close is not None else None,
        last_article=last,
        missing=[n for n in range(1, last + 1) if n not in plain],
        unresolved=len(unresolved),
        methods=methods,
    )
