"""Vector stores: in-memory (tests, evals) and pgvector (production)."""

from __future__ import annotations

from typing import Protocol

from .embeddings import cosine


class VectorStore(Protocol):
    def upsert(self, items: list[tuple[str, list[float], dict]]) -> None: ...
    def search(self, vector: list[float], k: int) -> list[tuple[str, float]]: ...
    def delete_policy(self, policy_id: str) -> None: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[list[float], dict]] = {}

    def upsert(self, items):
        for cid, vec, meta in items:
            self._rows[cid] = (vec, meta)

    def delete_policy(self, policy_id: str) -> None:
        self._rows = {k: v for k, v in self._rows.items() if v[1].get("policy_id") != policy_id}

    def search(self, vector, k):
        scored = [(cid, cosine(vector, v)) for cid, (v, _) in self._rows.items()]
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:k]

    def __len__(self) -> int:
        return len(self._rows)


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id        TEXT PRIMARY KEY,
    policy_id       TEXT NOT NULL,
    policy_version  TEXT NOT NULL,
    section         TEXT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(%(dim)s) NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS policy_chunks_policy_idx ON policy_chunks (policy_id);
CREATE INDEX IF NOT EXISTS policy_chunks_hnsw ON policy_chunks USING hnsw (embedding vector_cosine_ops);
"""


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


class PgVectorStore:
    """pgvector-backed store. Uses psycopg 3; import is lazy so tests don't need it."""

    def __init__(self, dsn: str, dim: int):
        import psycopg

        self.dim = dim
        self._conn = psycopg.connect(dsn, autocommit=True)

    def migrate(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(SCHEMA_SQL % {"dim": int(self.dim)})

    def upsert(self, items):
        with self._conn.cursor() as cur:
            for cid, vec, meta in items:
                cur.execute(
                    """INSERT INTO policy_chunks (chunk_id, policy_id, policy_version, section, content, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s::vector)
                       ON CONFLICT (chunk_id) DO UPDATE SET
                         policy_version = EXCLUDED.policy_version, section = EXCLUDED.section,
                         content = EXCLUDED.content, embedding = EXCLUDED.embedding, updated_at = now()""",
                    (cid, meta["policy_id"], meta["policy_version"], meta["section"], meta["text"], _vec_literal(vec)),
                )

    def delete_policy(self, policy_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM policy_chunks WHERE policy_id = %s", (policy_id,))

    def search(self, vector, k):
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT chunk_id, 1 - (embedding <=> %s::vector) AS score FROM policy_chunks "
                "ORDER BY embedding <=> %s::vector LIMIT %s",
                (_vec_literal(vector), _vec_literal(vector), k),
            )
            return [(r[0], float(r[1])) for r in cur.fetchall()]
