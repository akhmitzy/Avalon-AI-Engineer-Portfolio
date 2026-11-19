"""Okapi BM25 over policy chunks."""

from __future__ import annotations

import math
from collections import Counter

from .tokenize import tokenize


class BM25Index:
    # b=0.3 (weaker length normalization than the usual 0.75): policy sections are short and
    # the most important one ("Coverage criteria") is also the longest, so the default
    # penalized exactly the section reviewers ask about most.
    def __init__(self, k1: float = 1.5, b: float = 0.3):
        self.k1 = k1
        self.b = b
        self.ids: list[str] = []
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []
        self._df: Counter[str] = Counter()
        self._avgdl = 0.0

    def build(self, docs: list[tuple[str, str]]) -> BM25Index:
        self.ids, self._tf, self._len, self._df = [], [], [], Counter()
        for doc_id, text in docs:
            toks = tokenize(text)
            tf = Counter(toks)
            self.ids.append(doc_id)
            self._tf.append(tf)
            self._len.append(len(toks))
            self._df.update(tf.keys())
        self._avgdl = (sum(self._len) / len(self._len)) if self._len else 0.0
        return self

    def _idf(self, term: str) -> float:
        n = len(self.ids)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        q = tokenize(query)
        scores: list[tuple[str, float]] = []
        for i, doc_id in enumerate(self.ids):
            tf, dl = self._tf[i], self._len[i]
            s = 0.0
            for term in q:
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
                s += self._idf(term) * f * (self.k1 + 1) / denom
            if s > 0:
                scores.append((doc_id, s))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores[:k]
