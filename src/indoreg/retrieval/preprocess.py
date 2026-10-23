"""Tokenizers for lexical retrieval (FR-RET-1, ADR-007).

basic: lowercase word tokens.
id: basic, minus Indonesian function words, with the enclitic -nya and the
question particle -kah stripped ("datanya" -> "data", "bolehkah" -> "boleh").
No stemmer library (DI3): affix stripping beyond these two is error-prone on
legal terms ("pengendali", "pemrosesan") and is left out.
"""

import re
from collections.abc import Callable

WORD = re.compile(r"\w+")
SUFFIXES = ("nya", "kah")
MIN_STEM = 4  # never strip down to fewer letters than this

# Function words, question words and modal verbs. Not included on purpose:
# negations ("tidak", "bukan"), legal terms ("pasal", "ayat", "huruf"), numbers.
STOPWORDS_ID = frozenset(
    """
    yang dan di ke dari untuk dengan atau pada dalam ini itu adalah ialah merupakan
    sebagaimana dimaksud oleh akan dapat bagi tentang terhadap sesuai serta para
    setiap apa apakah bagaimana berapa kapan siapa mana kalau jika apabila bila harus
    juga telah sudah masih sebagai secara tersebut hal ada bisa boleh saja lagi
    agar supaya karena sehingga maka namun tetapi yaitu yakni antara kepada
    seorang sebuah suatu saat soal
    """.split()
)


def basic_tokens(text: str) -> list[str]:
    return WORD.findall(text.lower())


def _strip(token: str) -> str:
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= MIN_STEM:
            return token[: -len(suffix)]
    return token


def id_tokens(text: str) -> list[str]:
    out = []
    for tok in basic_tokens(text):
        tok = _strip(tok)
        if tok not in STOPWORDS_ID:
            out.append(tok)
    return out


TOKENIZERS: dict[str, Callable[[str], list[str]]] = {
    "basic": basic_tokens,
    "id": id_tokens,
}
