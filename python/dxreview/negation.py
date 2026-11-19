"""Negation cues shared by the offline extractor and the decision guard.

Known limitation, kept on purpose: we do not parse negation scope. A cue
AFTER the matched term ("mother diagnosed with ovarian cancer, genetic testing
never done") cannot be told apart from one that negates the term ("ovarian
cancer was ruled out"). Both are treated as AMBIGUOUS, which routes the case
to a clinician. That costs some accuracy (eval case ``neg-post-term-scope``)
but can never produce an unsafe approval.
"""

from __future__ import annotations

import re

# "negative" preceded by a hyphen is a tumor subtype (triple-negative, HER2-negative), not a negation.
NEGATION_CUE = re.compile(
    r"\b(?:no|not|never|denies|denied|without|absent|absence of|free of|negative for|"
    r"ruled out|rules out|rule out|r/o|unlikely|unconfirmed|declined)\b|(?<![-\w])negative\b",
    re.IGNORECASE,
)


def has_negation(text: str) -> bool:
    return bool(NEGATION_CUE.search(text))
