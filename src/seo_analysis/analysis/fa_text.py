"""Persian (Farsi) text helpers: normalization, tokenization, stop words, spelling variants.

Persian is written inconsistently. One word can appear with Arabic or Persian letters,
Arabic-Indic or Persian digits, with a half-space (ZWNJ, U+200C) or a plain space, or
with presentation-form glyphs. If those were counted as different words, real
duplicates would hide. Every comparison therefore goes through normalize() / tokenize().
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ZWNJ = "\u200c"
STOPWORDS_VERSION = "fa-stopwords-v1"
NORMALIZER_VERSION = "basic-v1"

_TRANSLATE = {
    0x064A: "\u06cc",  # Arabic yeh -> Persian yeh
    0x0649: "\u06cc",  # alef maksura -> Persian yeh
    0x0643: "\u06a9",  # Arabic kaf -> Persian kaf
    0x0629: "\u0647",  # teh marbuta -> heh
    0x06C0: "\u0647",  # heh with yeh above -> heh
    0x0623: "\u0627", 0x0625: "\u0627", 0x0671: "\u0627",  # hamza-on-alef variants -> alef
    0x200C: " ",       # half-space -> space (so "نرم‌افزار" == "نرم افزار")
}
_DELETE = (list(range(0x064B, 0x0660)) + [0x0670, 0x0640, 0x200D, 0x200E, 0x200F, 0x00AD]
           + list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A)))
for _c in _DELETE:  # diacritics, tatweel, ZWJ, bidi controls, soft hyphen
    _TRANSLATE[_c] = None
for _d in range(10):  # Arabic-Indic and Persian digits -> ASCII
    _TRANSLATE[0x0660 + _d] = str(_d)
    _TRANSLATE[0x06F0 + _d] = str(_d)

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def normalize(text: str) -> str:
    """Unify letter variants, digits, half-spaces and invisible marks; lower-case Latin."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return text.translate(_TRANSLATE).lower()


def tokenize(text: str, variants: dict | None = None) -> list[str]:
    toks = _WORD.findall(normalize(text))
    if not variants:
        return toks
    out: list[str] = []
    for t in toks:
        out.extend(variants.get(t, (t,)))
    return out


def persian_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _ARABIC_SCRIPT.match(c)) / len(letters)


def load_variants(path: str | Path | None) -> dict:
    """JSON file {"نرمافزار": "نرم افزار", ...} -> {token: (tokens...)}. User-approved only."""
    if not path or not Path(path).exists():
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for joined, split in raw.items():
        k, v = tokenize(joined), tokenize(split)
        if len(k) == 1 and v:
            out[k[0]] = tuple(v)
    return out


def load_stopwords(path: str | Path | None = None) -> set[str]:
    p = Path(path) if path else Path(__file__).with_name("stopwords_fa.txt")
    if not p.exists():
        return set()
    words = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            words.update(tokenize(line))
    return words


class HazmNormalizer:
    """Optional: Hazm fixes half-space spelling (میشود -> می‌شود, کتاب ها -> کتاب‌ها).
    Needs `pip install hazm` and Python 3.12 or 3.13. Never required."""

    def __init__(self, stem: bool = False):
        try:
            from hazm import Normalizer, Stemmer  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on the user's machine
            raise RuntimeError("Hazm is not installed or not supported on this Python "
                               "(needs 3.12 or 3.13): " + str(exc))
        self._norm = Normalizer()
        self._stem = Stemmer() if stem else None

    def normalize(self, text: str) -> str:
        return self._norm.normalize(text)

    def stem_token(self, token: str) -> str:
        return self._stem.stem(token) if self._stem else token
