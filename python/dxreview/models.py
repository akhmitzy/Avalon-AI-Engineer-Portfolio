"""Request, evidence and result schemas."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    """Possible outcomes. There is intentionally no DENY.

    An adverse determination must be made by a licensed clinician, so the
    system can only approve clearly supported requests, ask for missing
    documentation, or route to a human.
    """

    APPROVE = "APPROVE"
    NEEDS_INFO = "NEEDS_INFO"
    CLINICAL_REVIEW = "CLINICAL_REVIEW"


class EvidenceStatus(str, Enum):
    MET = "MET"
    NOT_MET = "NOT_MET"          # note explicitly contradicts the criterion
    NOT_FOUND = "NOT_FOUND"      # note is silent
    AMBIGUOUS = "AMBIGUOUS"      # extractor cannot tell (e.g. negation scope)


class CriterionEvidence(BaseModel):
    """What the extractor (LLM or offline) returns for one criterion."""

    criterion_id: str
    status: EvidenceStatus
    quote: str | None = Field(default=None, description="Verbatim span from the de-identified note")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: str | None = None


class CriterionResult(BaseModel):
    criterion_id: str
    text: str
    group: str
    status: EvidenceStatus
    quote: str | None = None
    quote_verified: bool = False
    confidence: float = 1.0
    notes: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    cpt_code: str = Field(pattern=r"^\d{4}[0-9A-Z]$")
    icd10_codes: list[str] = Field(default_factory=list)
    note: str = Field(min_length=1, max_length=200_000)
    payer: str | None = None


class ReviewResult(BaseModel):
    request_id: str
    decision: Decision
    reasons: list[str]
    policy_id: str | None = None
    policy_version: str | None = None
    prompt_version: str
    model: str
    criteria: list[CriterionResult] = Field(default_factory=list)
    missing_criteria: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    phi_redactions: dict[str, int] = Field(default_factory=dict)
    note_sha256: str
    trace: list[dict] = Field(default_factory=list)


class CopilotAnswer(BaseModel):
    question: str
    answer: str
    citations: list[dict]
    model: str
