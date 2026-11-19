"""DxReview: agentic prior-authorization review for lab and genetic tests.

The LLM extracts per-criterion evidence with verbatim quotes from a
de-identified note. Deterministic code makes the decision:
APPROVE, NEEDS_INFO or CLINICAL_REVIEW. There is no automated DENY.
"""

__version__ = "0.3.0"
