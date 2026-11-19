"""Prompt-injection defences for clinical notes.

Two steps, and the ORDER MATTERS:

1. ``scan_injection`` looks at the raw (PHI-scrubbed) note for instructions
   aimed at the model, including attempts to close the ``<clinical_note>``
   delimiter and open a fake ``<system>`` block.
2. ``neutralize_delimiters`` then escapes angle-bracket tags so the note cannot
   break out of its delimiter inside the prompt.

An earlier version ran (2) before (1). Neutralizing turned ``</clinical_note>``
into ``&lt;/clinical_note&gt;``, which erased exactly what the scan looks for,
so delimiter-spoofing notes passed the scan. The eval suite caught it
(``inj-delimiter-spoof``) and ``test_safety.py`` pins the order.

A flagged note is never rejected or denied: it is routed to CLINICAL_REVIEW.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override_instructions", re.compile(
        r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|all|system)\b[^.\n]{0,20}\b(?:instructions?|prompts?|rules?|guidelines?)",
        re.IGNORECASE)),
    ("role_reassignment", re.compile(r"\byou are (?:now|no longer)\b|\bact as (?:an?|the)\b[^.\n]{0,30}\b(?:reviewer|approver|assistant|model)", re.IGNORECASE)),
    ("decision_coercion", re.compile(
        r"\b(?:must|should|always|please)\s+(?:be\s+)?(?:approve|approved|auto-?approve)\b|\b(?:mark|set|output|return|respond with)\b[^.\n]{0,25}\b(?:APPROVE|MET)\b|\bcriteria (?:are|is) (?:all )?met\b[^.\n]{0,20}\bregardless\b",
        re.IGNORECASE)),
    ("delimiter_spoof", re.compile(r"</?\s*(?:clinical_note|system|assistant|user|instructions?|policy|criteria)\s*>", re.IGNORECASE)),
    ("chat_template_tokens", re.compile(r"<\|(?:im_start|im_end|system|endoftext)\|>|\[/?INST\]|\bHuman:|\bAssistant:", re.IGNORECASE)),
]

_TAG = re.compile(r"[<>]")


@dataclass
class InjectionScan:
    flagged: bool
    signals: list[str] = field(default_factory=list)


def scan_injection(note: str) -> InjectionScan:
    signals = [name for name, pat in _INJECTION_PATTERNS if pat.search(note)]
    return InjectionScan(flagged=bool(signals), signals=signals)


def neutralize_delimiters(note: str) -> str:
    """Escape angle brackets so the note cannot open or close prompt tags."""
    return _TAG.sub(lambda m: "&lt;" if m.group(0) == "<" else "&gt;", note)


def prepare_note(note: str) -> tuple[str, InjectionScan]:
    """Scan first, then neutralize. Do not reorder (see module docstring)."""
    scan = scan_injection(note)
    return neutralize_delimiters(note), scan


__all__ = ["InjectionScan", "neutralize_delimiters", "prepare_note", "scan_injection"]
