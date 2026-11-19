"""Model providers. Select with DXREVIEW_PROVIDER = offline | anthropic | bedrock."""

from __future__ import annotations

import os

from .base import ExtractionError, Extractor, TextGenerator, parse_evidence
from .offline import OfflineExtractor


class OfflineGenerator:
    """Extractive stand-in for the copilot's answer model."""

    model_id = "offline-extractive/v1"

    def generate(self, system: str, user: str, max_tokens: int = 800) -> str:
        raise NotImplementedError("the copilot builds offline answers itself")


def get_extractor(name: str | None = None) -> Extractor:
    name = (name or os.environ.get("DXREVIEW_PROVIDER", "offline")).lower()
    if name == "offline":
        return OfflineExtractor()
    if name == "anthropic":
        from .anthropic_provider import AnthropicExtractor
        return AnthropicExtractor()
    if name == "bedrock":
        from .bedrock_provider import BedrockExtractor
        return BedrockExtractor()
    raise ValueError(f"unknown provider {name!r}")


def get_generator(name: str | None = None) -> TextGenerator:
    name = (name or os.environ.get("DXREVIEW_PROVIDER", "offline")).lower()
    if name == "offline":
        return OfflineGenerator()
    if name == "anthropic":
        from .anthropic_provider import AnthropicGenerator
        return AnthropicGenerator()
    if name == "bedrock":
        from .bedrock_provider import BedrockGenerator
        return BedrockGenerator()
    raise ValueError(f"unknown provider {name!r}")


__all__ = [
    "ExtractionError",
    "Extractor",
    "OfflineExtractor",
    "OfflineGenerator",
    "TextGenerator",
    "get_extractor",
    "get_generator",
    "parse_evidence",
]
