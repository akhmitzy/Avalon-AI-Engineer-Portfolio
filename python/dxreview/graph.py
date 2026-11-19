"""The review graph.

    scrub_phi -> scan_and_neutralize -> load_policy -> retrieve_context
              -> extract_evidence -> verify_and_decide -> audit

Each node takes and returns the shared ``ReviewState``. Nodes that hit a
problem set a flag instead of raising, and the graph short-circuits to the
decision node, so every request ends in a decision (never a crash, never a
DENY). Each node's duration is recorded in ``trace``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from . import phi
from .decision import apply_guards, decide
from .models import CriterionResult, Decision, ReviewRequest, ReviewResult
from .policies import Policy, PolicyStore, default_store
from .prompts import PROMPT_VERSION
from .providers import ExtractionError, Extractor, get_extractor
from .rag import HybridRetriever
from .safety import prepare_note

log = logging.getLogger("dxreview.audit")


@dataclass
class ReviewState:
    request: ReviewRequest
    scrubbed_note: str = ""
    model_note: str = ""
    phi_counts: dict[str, int] = field(default_factory=dict)
    policy: Policy | None = None
    context_chunks: list[str] = field(default_factory=list)
    criteria: list[CriterionResult] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    decision: Decision | None = None
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    done: bool = False


Node = Callable[[ReviewState], ReviewState]


class ReviewGraph:
    def __init__(self, store: PolicyStore | None = None, extractor: Extractor | None = None,
                 retriever: HybridRetriever | None = None, audit_sink: Callable[[dict], None] | None = None):
        self.store = store or default_store()
        self.extractor = extractor or get_extractor()
        self.retriever = retriever or HybridRetriever(self.store)
        self.audit_sink = audit_sink or (lambda rec: log.info(json.dumps(rec, sort_keys=True)))
        self.nodes: list[tuple[str, Node]] = [
            ("scrub_phi", self.scrub_phi),
            ("scan_and_neutralize", self.scan_and_neutralize),
            ("load_policy", self.load_policy),
            ("retrieve_context", self.retrieve_context),
            ("extract_evidence", self.extract_evidence),
            ("verify_and_decide", self.verify_and_decide),
            ("audit", self.audit),
        ]
        self._always_run = {"verify_and_decide", "audit"}

    # nodes ---------------------------------------------------------------
    def scrub_phi(self, s: ReviewState) -> ReviewState:
        r = phi.scrub(s.request.note)
        s.scrubbed_note, s.phi_counts = r.text, r.counts
        return s

    def scan_and_neutralize(self, s: ReviewState) -> ReviewState:
        s.model_note, scan = prepare_note(s.scrubbed_note)
        if scan.flagged:
            s.flags.extend(f"prompt_injection:{sig}" for sig in scan.signals)
            s.done = True  # don't send a hostile note to the model at all
        return s

    def load_policy(self, s: ReviewState) -> ReviewState:
        s.policy = self.store.for_cpt(s.request.cpt_code)
        if s.policy is None:
            s.flags.append(f"no_policy_for_cpt:{s.request.cpt_code}")
            s.done = True
        return s

    def retrieve_context(self, s: ReviewState) -> ReviewState:
        assert s.policy is not None
        query = " ".join(c.text for c in s.policy.criteria)
        s.context_chunks = [h.chunk.chunk_id for h in self.retriever.search(query, k=3, policy_id=s.policy.id)]
        return s

    def extract_evidence(self, s: ReviewState) -> ReviewState:
        assert s.policy is not None
        try:
            evidence = self.extractor.extract(s.policy, s.model_note)
        except ExtractionError as e:
            s.flags.append(f"extraction_error:{e}")
            s.done = True
            return s
        s.criteria = apply_guards(s.policy, evidence, s.model_note)
        return s

    def verify_and_decide(self, s: ReviewState) -> ReviewState:
        if s.policy is None or s.flags:
            s.decision, s.reasons, s.missing = Decision.CLINICAL_REVIEW, [f"safety_flag:{f}" for f in s.flags], []
        else:
            s.decision, s.reasons, s.missing = decide(s.policy, s.criteria, s.flags)
        return s

    def audit(self, s: ReviewState) -> ReviewState:
        self.audit_sink({
            "event": "review_decision",
            "request_id": s.request.request_id,
            "cpt_code": s.request.cpt_code,
            "decision": s.decision.value if s.decision else None,
            "reasons": s.reasons,
            "policy_id": s.policy.id if s.policy else None,
            "policy_version": s.policy.version if s.policy else None,
            "prompt_version": PROMPT_VERSION,
            "model": self.extractor.model_id,
            "note_sha256": _sha(s.scrubbed_note),
            "phi_redactions": s.phi_counts,
            "flags": s.flags,
        })
        return s

    # driver --------------------------------------------------------------
    def run(self, request: ReviewRequest) -> ReviewResult:
        s = ReviewState(request=request)
        for name, node in self.nodes:
            if s.done and name not in self._always_run:
                s.trace.append({"node": name, "skipped": True})
                continue
            t0 = time.perf_counter()
            s = node(s)
            s.trace.append({"node": name, "ms": round((time.perf_counter() - t0) * 1000, 3)})
        assert s.decision is not None
        return ReviewResult(
            request_id=request.request_id,
            decision=s.decision,
            reasons=s.reasons,
            policy_id=s.policy.id if s.policy else None,
            policy_version=s.policy.version if s.policy else None,
            prompt_version=PROMPT_VERSION,
            model=self.extractor.model_id,
            criteria=s.criteria,
            missing_criteria=s.missing,
            flags=s.flags,
            phi_redactions=s.phi_counts,
            note_sha256=_sha(s.scrubbed_note),
            trace=s.trace,
        )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
