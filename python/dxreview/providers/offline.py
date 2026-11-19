"""Offline, deterministic extractor.

Stands in for the LLM in the eval gate and in tests so results are
reproducible and need no API key. It uses each criterion's
``offline_patterns`` and the shared negation cues. It is intentionally simple:
the point of the gate is to test everything AROUND the model (scrubbing,
injection handling, quote verification, the decision rules), and to catch
regressions there. Live evals (``--provider anthropic|bedrock``) test the model.
"""

from __future__ import annotations

import re

from ..models import CriterionEvidence, EvidenceStatus
from ..negation import NEGATION_CUE
from ..policies import Policy

# Sentence-ish spans. A period followed by a non-space (Z80.3, 4.5) does not end a span.
_SPAN = re.compile(r"(?:[^.!?;\n]|\.(?=\S))+[.!?]?")
_CLAUSE_BREAK = re.compile(r"[,:]")


def _spans(note: str):
    for m in _SPAN.finditer(note):
        text = m.group(0).strip()
        if text:
            start = m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))
            yield start, text


class OfflineExtractor:
    model_id = "offline-rules/v2"

    def __init__(self) -> None:
        self._cache: dict[str, list[re.Pattern[str]]] = {}

    def _patterns(self, policy: Policy, cid: str, raw: tuple[str, ...]) -> list[re.Pattern[str]]:
        key = f"{policy.id}:{policy.version}:{cid}"
        if key not in self._cache:
            self._cache[key] = [re.compile(p, re.IGNORECASE) for p in raw]
        return self._cache[key]

    def extract(self, policy: Policy, note: str) -> list[CriterionEvidence]:
        spans = list(_spans(note))
        out = []
        for c in policy.criteria:
            pats = self._patterns(policy, c.id, c.offline_patterns)
            excl = self._patterns(policy, c.id + ":exclude", c.offline_exclude)
            best: CriterionEvidence | None = None
            for _, sentence in spans:
                if any(x.search(sentence) for x in excl):
                    continue
                for pat in pats:
                    m = pat.search(sentence)
                    if not m:
                        continue
                    breaks = [b.end() for b in _CLAUSE_BREAK.finditer(sentence, 0, m.start())]
                    clause_start = breaks[-1] if breaks else 0
                    before = sentence[clause_start:m.end()]
                    after = sentence[m.end():]
                    if NEGATION_CUE.search(before):
                        ev = CriterionEvidence(criterion_id=c.id, status=EvidenceStatus.NOT_MET, quote=sentence,
                                               confidence=0.9, rationale="negation cue before term")
                    elif NEGATION_CUE.search(after):
                        ev = CriterionEvidence(criterion_id=c.id, status=EvidenceStatus.AMBIGUOUS, quote=sentence,
                                               confidence=0.5, rationale="negation cue after term; scope unclear")
                    else:
                        ev = CriterionEvidence(criterion_id=c.id, status=EvidenceStatus.MET, quote=sentence,
                                               confidence=0.95, rationale="pattern match")
                    # Prefer a clean MET anywhere in the note over a negated mention.
                    if best is None or (ev.status == EvidenceStatus.MET and best.status != EvidenceStatus.MET):
                        best = ev
                    break
                if best is not None and best.status == EvidenceStatus.MET:
                    break
            out.append(best or CriterionEvidence(criterion_id=c.id, status=EvidenceStatus.NOT_FOUND))
        return out
