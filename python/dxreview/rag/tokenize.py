"""Tokenizer for clinical and policy text.

Gene and code names carry digits and slashes (BRCA1/BRCA2, CYP2C19, MSI-H,
81162). The first version split only on whitespace and kept ``BRCA1/BRCA2``
as one token, so a query for "BRCA2" never matched the BRCA policy's coverage
section by keyword. The copilot citation metric dropped on BRCA questions and
pointed at it. Now slashes always split, and hyphenated terms emit both the
parts and the joined form (``msi-h`` -> ``msi``, ``h``, ``msih``).
"""

from __future__ import annotations

import re

_STOP = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with", "what", "which", "when", "who", "how", "does", "do", "can", "should", "i", "we", "you", "they", "before", "after", "need", "needed", "required", "require", "requires", "must", "any"]
)
_SPLIT = re.compile(r"[^\w\-]+")

# Light suffix stripping so "covered"/"coverage" and "documented"/"documentation"
# meet. Tokens with digits (gene names, codes) are never stemmed.
_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ages", "age", "ness", "ies", "ied", "ed", "es", "s")

# Small domain synonym table, applied after stemming. Keep it short and reviewed.
_SYNONYMS = {
    "often": "frequenc", "frequency": "frequenc", "frequenc": "frequenc",
    "nipt": "cfdna", "cell-free": "cfdna",
    "twin": "multipl", "twins": "multipl", "multiple": "multipl",
    "pgx": "pharmacogenomic",
}


def stem(tok: str) -> str:
    if tok in _SYNONYMS:
        return _SYNONYMS[tok]
    if any(ch.isdigit() for ch in tok) or len(tok) <= 4:
        return tok
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            tok = tok[: -len(suf)]
            break
    if len(tok) > 4 and tok.endswith("e"):
        tok = tok[:-1]
    return _SYNONYMS.get(tok, tok)


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in _raw_tokens(text)]


def _raw_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _SPLIT.split(text.lower()):
        raw = raw.strip("-_")
        if not raw:
            continue
        if raw in _SYNONYMS:
            tokens.append(raw)
        elif "-" in raw:
            parts = [p for p in raw.split("-") if p]
            tokens.extend(p for p in parts if p not in _STOP)
            joined = "".join(parts)
            if len(parts) > 1 and joined:
                tokens.append(joined)
        elif raw not in _STOP:
            tokens.append(raw)
    return tokens
