"""Claude through the Anthropic API."""

from __future__ import annotations

import os

from ..models import CriterionEvidence
from ..policies import Policy
from ..prompts import SYSTEM_PROMPT, TOOL_DESCRIPTION, TOOL_NAME, TOOL_SCHEMA, build_user_message
from .base import ExtractionError, parse_evidence

DEFAULT_MODEL = os.environ.get("DXREVIEW_ANTHROPIC_MODEL", "claude-sonnet-5-5")


class AnthropicExtractor:
    def __init__(self, model: str = DEFAULT_MODEL, client=None, max_tokens: int = 2000):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self._client = client
        self.model_id = model
        self.max_tokens = max_tokens

    def extract(self, policy: Policy, note: str) -> list[CriterionEvidence]:
        try:
            resp = self._client.messages.create(
                model=self.model_id,
                max_tokens=self.max_tokens,
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=[{"name": TOOL_NAME, "description": TOOL_DESCRIPTION, "input_schema": TOOL_SCHEMA}],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": build_user_message(policy, note)}],
            )
        except Exception as e:  # network, auth, rate limit
            raise ExtractionError(f"anthropic call failed: {type(e).__name__}") from e
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
                return parse_evidence(policy, block.input)
        raise ExtractionError("model did not call record_evidence")


class AnthropicGenerator:
    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self._client = client
        self.model_id = model

    def generate(self, system: str, user: str, max_tokens: int = 800) -> str:
        resp = self._client.messages.create(
            model=self.model_id, max_tokens=max_tokens, temperature=0, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
