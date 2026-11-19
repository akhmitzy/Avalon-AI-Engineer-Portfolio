"""Policy copilot: answers reviewer questions about coverage policies, with citations.

Answers may only cite chunks that retrieval returned. Citations the model
invents are dropped; an answer left with no valid citation is replaced by a
refusal, because an uncited policy claim is worse than no answer.
"""

from __future__ import annotations

import re

from .models import CopilotAnswer
from .providers import OfflineGenerator, TextGenerator, get_generator
from .rag import HybridRetriever, tokenize

COPILOT_PROMPT_VERSION = "policy-copilot/v2"

SYSTEM = """You answer questions from prior-authorization reviewers about lab and genetic test coverage policies.
Use ONLY the policy excerpts provided. After every claim, cite the excerpt id in square brackets, e.g. [LAB-GEN-001#coverage-criteria].
If the excerpts do not answer the question, say "The policies provided do not cover this." Do not give medical advice about individual patients."""

_CITE = re.compile(r"\[([A-Z]{3}-[A-Z]{3,4}-\d{3}#[a-z0-9-]+)\]")
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
NO_ANSWER = "The policies provided do not cover this."


class PolicyCopilot:
    def __init__(self, retriever: HybridRetriever, generator: TextGenerator | None = None, k: int = 4):
        self.retriever = retriever
        self.generator = generator or get_generator()
        self.k = k

    def ask(self, question: str, policy_id: str | None = None) -> CopilotAnswer:
        hits = self.retriever.search(question, k=self.k, policy_id=policy_id)
        if not hits:
            return CopilotAnswer(question=question, answer=NO_ANSWER, citations=[], model=self.generator.model_id)
        allowed = {h.chunk.chunk_id: h for h in hits}
        if isinstance(self.generator, OfflineGenerator):
            answer, cited = self._extractive(question, hits)
        else:
            excerpts = "\n\n".join(f"<excerpt id=\"{h.chunk.chunk_id}\">\n{h.chunk.text}\n</excerpt>" for h in hits)
            answer = self.generator.generate(SYSTEM, f"{excerpts}\n\nQuestion: {question}")
            cited = [c for c in dict.fromkeys(_CITE.findall(answer))]
            invalid = [c for c in cited if c not in allowed]
            for c in invalid:
                answer = answer.replace(f"[{c}]", "")
            cited = [c for c in cited if c in allowed]
            if not cited and NO_ANSWER not in answer:
                answer = NO_ANSWER
        citations = [{
            "chunk_id": cid,
            "policy_id": allowed[cid].chunk.policy_id,
            "policy_version": allowed[cid].chunk.policy_version,
            "section": allowed[cid].chunk.section,
        } for cid in cited]
        return CopilotAnswer(question=question, answer=answer.strip(), citations=citations, model=self.generator.model_id)

    @staticmethod
    def _extractive(question: str, hits, sections: int = 2) -> tuple[str, list[str]]:
        """Offline answer: quote the best-matching sentence from each of the top
        retrieved sections, in retrieval order. Citation quality therefore
        measures retrieval quality directly, which is what the offline eval is for.
        """
        q = set(tokenize(question))
        picked = []
        for h in hits[:sections]:
            body = h.chunk.text.split("\n", 1)[-1]
            best, best_overlap = None, 0.0
            for sent in _SENT.split(body):
                sent = sent.strip(" -*")
                toks = set(tokenize(sent))
                if len(toks) < 3:
                    continue
                overlap = len(q & toks) / (len(q) or 1)
                if best is None or overlap > best_overlap:
                    best, best_overlap = sent, overlap
            # A section can match on its heading alone ("documented" -> "Documentation
            # requirements"); then its first sentence is the answer.
            if best is not None:
                picked.append((best, h.chunk.chunk_id))
        if not picked:
            return NO_ANSWER, []
        return " ".join(f"{s} [{cid}]" for s, cid in picked), [cid for _, cid in picked]
