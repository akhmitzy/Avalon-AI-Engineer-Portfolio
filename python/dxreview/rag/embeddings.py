"""Embedding providers.

``HashingEmbedder`` is deterministic and offline (feature hashing of tokens and
character trigrams). It keeps the eval gate reproducible and needs no network.
``BedrockTitanEmbedder`` is the production option (Amazon Titan Text
Embeddings v2 through Bedrock, inside the VPC).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Protocol

from .tokenize import tokenize


class Embedder(Protocol):
    dim: int
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _h(s: str, dim: int) -> tuple[int, float]:
    d = hashlib.blake2b(s.encode(), digest_size=8).digest()
    v = int.from_bytes(d, "little")
    return v % dim, (1.0 if (v >> 63) & 1 else -1.0)


class HashingEmbedder:
    name = "hashing-v1"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self.dim
            for tok in tokenize(t):
                i, s = _h("t:" + tok, self.dim)
                vec[i] += s
                padded = f"#{tok}#"
                for j in range(len(padded) - 2):
                    i, s = _h("c:" + padded[j:j + 3], self.dim)
                    vec[i] += 0.3 * s
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class BedrockTitanEmbedder:
    name = "amazon.titan-embed-text-v2:0"

    def __init__(self, dim: int = 1024, region: str | None = None, client=None):
        self.dim = dim
        if client is None:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=region)
        self._client = client

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            resp = self._client.invoke_model(
                modelId=self.name,
                body=json.dumps({"inputText": t, "dimensions": self.dim, "normalize": True}),
            )
            out.append(json.loads(resp["body"].read())["embedding"])
        return out


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
