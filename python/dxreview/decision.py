"""Deterministic decision rules. The model never decides.

Order of precedence (first match wins):
  1. Safety flags (injection, extraction failure, no policy)  -> CLINICAL_REVIEW
  2. Any criterion that blocks its group with NOT_MET or AMBIGUOUS
     (including MET evidence downgraded by the guards below) -> CLINICAL_REVIEW
  3. Any group not satisfied because evidence is NOT_FOUND    -> NEEDS_INFO
  4. Every group satisfied with verified evidence             -> APPROVE

Guards applied to every MET before the rules run:
  * the quote must appear verbatim in the note the model saw (whitespace-normalized)
  * the quote must not contain a negation cue
  * confidence must be at least ``MIN_CONFIDENCE``
A MET that fails a guard becomes AMBIGUOUS.

There is no DENY. See ``models.Decision``.
"""

from __future__ import annotations

import re

from .models import CriterionEvidence, CriterionResult, Decision, EvidenceStatus
from .negation import has_negation
from .policies import Policy

MIN_CONFIDENCE = 0.7
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s).strip().lower()


def verify_quote(quote: str | None, note: str) -> bool:
    if not quote or len(quote.strip()) < 4:
        return False
    return _norm(quote) in _norm(note)


def apply_guards(policy: Policy, evidence: list[CriterionEvidence], note: str) -> list[CriterionResult]:
    by_id = {e.criterion_id: e for e in evidence}
    results = []
    for c in policy.criteria:
        ev = by_id.get(c.id) or CriterionEvidence(criterion_id=c.id, status=EvidenceStatus.NOT_FOUND)
        status = ev.status
        notes: list[str] = []
        verified = verify_quote(ev.quote, note) if ev.quote else False
        if status in (EvidenceStatus.MET, EvidenceStatus.NOT_MET, EvidenceStatus.AMBIGUOUS) and not verified:
            notes.append("quote_not_found_in_note")
            if status == EvidenceStatus.MET:
                status = EvidenceStatus.AMBIGUOUS
        if status == EvidenceStatus.MET:
            if has_negation(ev.quote or ""):
                notes.append("negation_in_quote")
                status = EvidenceStatus.AMBIGUOUS
            elif ev.confidence < MIN_CONFIDENCE:
                notes.append("low_confidence")
                status = EvidenceStatus.AMBIGUOUS
        results.append(CriterionResult(
            criterion_id=c.id, text=c.text, group=c.group, status=status,
            quote=ev.quote, quote_verified=verified, confidence=ev.confidence, notes=notes,
        ))
    return results


def decide(policy: Policy, results: list[CriterionResult], flags: list[str]) -> tuple[Decision, list[str], list[str]]:
    """Return (decision, reasons, missing_criterion_ids)."""
    if flags:
        return Decision.CLINICAL_REVIEW, [f"safety_flag:{f}" for f in flags], []

    review_reasons: list[str] = []
    missing: list[str] = []
    groups: dict[str, list[CriterionResult]] = {}
    for r in results:
        groups.setdefault(r.group, []).append(r)

    for group, items in groups.items():
        if group == "required":
            for r in items:
                if r.status in (EvidenceStatus.NOT_MET, EvidenceStatus.AMBIGUOUS):
                    review_reasons.append(f"{r.criterion_id}:{r.status.value.lower()}")
                elif r.status == EvidenceStatus.NOT_FOUND:
                    missing.append(r.criterion_id)
        else:
            if any(r.status == EvidenceStatus.MET for r in items):
                continue
            blockers = [r for r in items if r.status in (EvidenceStatus.NOT_MET, EvidenceStatus.AMBIGUOUS)]
            if blockers:
                review_reasons.extend(f"{r.criterion_id}:{r.status.value.lower()}" for r in blockers)
            else:
                missing.extend(r.criterion_id for r in items)

    if review_reasons:
        return Decision.CLINICAL_REVIEW, review_reasons, missing
    if missing:
        return Decision.NEEDS_INFO, [f"missing:{m}" for m in missing], missing
    return Decision.APPROVE, ["all_criteria_met_with_verified_quotes"], []
