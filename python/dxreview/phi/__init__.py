"""PHI scrubber (Python reference implementation).

The pattern table lives in ``shared/phi_patterns.json`` and is shared with the
Rust scrubber in ``rust/phi-scrubber``. Both implementations are tested against
the same fixtures (``shared/fixtures/phi_cases.json``) so they cannot drift.

The scrubber is deliberately conservative: it runs before anything leaves the
trust boundary (LLM calls, logs, audit records). Over-redaction is acceptable,
under-redaction is not.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_GROUP_REF = re.compile(r"\$\{(\d+)\}")


def _patterns_path() -> Path:
    env = os.environ.get("DXREVIEW_PHI_PATTERNS")
    if env:
        return Path(env)
    bundled = Path(__file__).with_name("patterns.json")
    if bundled.exists():
        return bundled
    # Running from a source checkout: python/dxreview/phi -> repo root
    return Path(__file__).resolve().parents[3] / "shared" / "phi_patterns.json"


@dataclass(frozen=True)
class _Pattern:
    kind: str
    regex: re.Pattern[str]
    replacement: str


@lru_cache(maxsize=1)
def load_patterns() -> tuple[str, tuple[_Pattern, ...]]:
    data = json.loads(_patterns_path().read_text(encoding="utf-8"))
    compiled = tuple(
        _Pattern(
            kind=p["kind"],
            regex=re.compile(p["regex"]),
            # Rust uses ${1}; Python uses \g<1>.
            replacement=_GROUP_REF.sub(r"\\g<\1>", p["replacement"]),
        )
        for p in data["patterns"]
    )
    return data["version"], compiled


@dataclass
class ScrubResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    patterns_version: str = ""

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def scrub(text: str) -> ScrubResult:
    """Replace PHI in ``text`` with typed placeholders.

    Returns the scrubbed text and per-kind redaction counts. The counts are safe
    to log; the original values are never retained.
    """
    version, patterns = load_patterns()
    counts: dict[str, int] = {}
    for p in patterns:
        text, n = p.regex.subn(p.replacement, text)
        if n:
            counts[p.kind] = counts.get(p.kind, 0) + n
    return ScrubResult(text=text, counts=counts, patterns_version=version)


__all__ = ["ScrubResult", "load_patterns", "scrub"]
