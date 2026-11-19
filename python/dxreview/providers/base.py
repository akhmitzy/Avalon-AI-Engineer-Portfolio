from __future__ import annotations

from typing import Protocol

from pydantic import ValidationError

from ..models import CriterionEvidence, EvidenceStatus
from ..policies import Policy


class ExtractionError(RuntimeError):
    """Provider failed or returned unusable output. Routed to CLINICAL_REVIEW."""


class Extractor(Protocol):
    model_id: str

    def extract(self, policy: Policy, note: str) -> list[CriterionEvidence]:
        """``note`` is PHI-scrubbed and delimiter-neutralized."""


class TextGenerator(Protocol):
    model_id: str

    def generate(self, system: str, user: str, max_tokens: int = 800) -> str: ...


def parse_evidence(policy: Policy, raw: dict) -> list[CriterionEvidence]:
    """Validate tool output and make it total over the policy's criteria.

    Unknown criterion ids are dropped; missing ones become NOT_FOUND; duplicates
    keep the most conservative status.
    """
    items = raw.get("evidence") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise ExtractionError("tool output has no evidence list")
    known = {c.id for c in policy.criteria}
    rank = {EvidenceStatus.NOT_MET: 0, EvidenceStatus.AMBIGUOUS: 1, EvidenceStatus.NOT_FOUND: 2, EvidenceStatus.MET: 3}
    out: dict[str, CriterionEvidence] = {}
    for item in items:
        try:
            ev = CriterionEvidence.model_validate(item)
        except ValidationError as e:
            raise ExtractionError(f"invalid evidence item: {e.errors()[0]['msg']}") from e
        if ev.criterion_id not in known:
            continue
        prev = out.get(ev.criterion_id)
        if prev is None or rank[ev.status] < rank[prev.status]:
            out[ev.criterion_id] = ev
    return [out.get(c.id) or CriterionEvidence(criterion_id=c.id, status=EvidenceStatus.NOT_FOUND)
            for c in policy.criteria]
