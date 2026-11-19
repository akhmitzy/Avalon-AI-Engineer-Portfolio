"""Hybrid retrieval: BM25 + vectors, fused with Reciprocal Rank Fusion."""

from __future__ import annotations

from dataclasses import dataclass

from ..policies import PolicyChunk, PolicyStore
from .bm25 import BM25Index
from .embeddings import Embedder, HashingEmbedder
from .tokenize import tokenize
from .vectorstore import InMemoryVectorStore, VectorStore

RRF_K = 60


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (k + rank)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


@dataclass
class Hit:
    chunk: PolicyChunk
    score: float
    bm25_rank: int | None
    vector_rank: int | None


class HybridRetriever:
    def __init__(self, store: PolicyStore, embedder: Embedder | None = None,
                 vectors: VectorStore | None = None, candidates: int = 20):
        self.store = store
        self.embedder = embedder or HashingEmbedder()
        self.vectors = vectors or InMemoryVectorStore()
        self.candidates = candidates
        self.bm25 = BM25Index()
        self._chunks: dict[str, PolicyChunk] = {}
        self.reindex()

    def reindex(self, policy_ids: list[str] | None = None) -> int:
        """(Re)build indexes. Called at startup and by the n8n re-index workflow."""
        chunks = self.store.chunks()
        targets = [c for c in chunks if policy_ids is None or c.policy_id in policy_ids]
        for pid in {c.policy_id for c in targets}:
            self.vectors.delete_policy(pid)
        vecs = self.embedder.embed([c.text for c in targets]) if targets else []
        self.vectors.upsert([
            (c.chunk_id, v, {"policy_id": c.policy_id, "policy_version": c.policy_version,
                             "section": c.section, "text": c.text})
            for c, v in zip(targets, vecs, strict=True)
        ])
        self._chunks = {c.chunk_id: c for c in chunks}
        # Field boost: the section heading counts three times in the keyword index.
        self.bm25.build([(c.chunk_id, f"{c.section} {c.section} {c.text}") for c in chunks])
        return len(targets)

    def search(self, query: str, k: int = 5, policy_id: str | None = None) -> list[Hit]:
        bm = [cid for cid, _ in self.bm25.search(query, self.candidates)]
        vec = [cid for cid, _ in self.vectors.search(self.embedder.embed([query])[0], self.candidates)]
        if policy_id:
            bm = [c for c in bm if self._chunks[c].policy_id == policy_id]
            vec = [c for c in vec if self._chunks[c].policy_id == policy_id]
        hits = []
        for cid, score in rrf([bm, vec])[:k]:
            hits.append(Hit(
                chunk=self._chunks[cid], score=score,
                bm25_rank=bm.index(cid) + 1 if cid in bm else None,
                vector_rank=vec.index(cid) + 1 if cid in vec else None,
            ))
        return hits


__all__ = ["Hit", "HybridRetriever", "rrf", "tokenize"]
