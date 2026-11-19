"""Claude through Amazon Bedrock (Converse API). Keeps PHI-adjacent traffic in the AWS account."""

from __future__ import annotations

import os

from ..models import CriterionEvidence
from ..policies import Policy
from ..prompts import SYSTEM_PROMPT, TOOL_DESCRIPTION, TOOL_NAME, TOOL_SCHEMA, build_user_message
from .base import ExtractionError, parse_evidence

DEFAULT_MODEL = os.environ.get("DXREVIEW_BEDROCK_MODEL", "anthropic.claude-sonnet-5-5-v1:0")


def _client(region: str | None):
    import boto3
    return boto3.client("bedrock-runtime", region_name=region or os.environ.get("AWS_REGION", "us-east-1"))


class BedrockExtractor:
    def __init__(self, model: str = DEFAULT_MODEL, client=None, region: str | None = None, max_tokens: int = 2000):
        self._client = client or _client(region)
        self.model_id = model
        self.max_tokens = max_tokens

    def extract(self, policy: Policy, note: str) -> list[CriterionEvidence]:
        try:
            resp = self._client.converse(
                modelId=self.model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": build_user_message(policy, note)}]}],
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": 0},
                toolConfig={
                    "tools": [{"toolSpec": {"name": TOOL_NAME, "description": TOOL_DESCRIPTION,
                                            "inputSchema": {"json": TOOL_SCHEMA}}}],
                    "toolChoice": {"tool": {"name": TOOL_NAME}},
                },
            )
        except Exception as e:
            raise ExtractionError(f"bedrock call failed: {type(e).__name__}") from e
        for block in resp.get("output", {}).get("message", {}).get("content", []):
            tu = block.get("toolUse")
            if tu and tu.get("name") == TOOL_NAME:
                return parse_evidence(policy, tu.get("input", {}))
        raise ExtractionError("model did not call record_evidence")


class BedrockGenerator:
    def __init__(self, model: str = DEFAULT_MODEL, client=None, region: str | None = None):
        self._client = client or _client(region)
        self.model_id = model

    def generate(self, system: str, user: str, max_tokens: int = 800) -> str:
        resp = self._client.converse(
            modelId=self.model_id, system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        return "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
