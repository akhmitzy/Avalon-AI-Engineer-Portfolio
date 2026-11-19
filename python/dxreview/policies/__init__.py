"""Coverage policy loading and chunking.

Policies are markdown files with YAML front matter. The front matter holds the
structured, machine-checked criteria (ids, groups, text). The body holds the
human-readable policy that the RAG index and the copilot cite.

Criterion groups:
  * ``required``: every criterion in the group must be MET.
  * any other name: at least one criterion in that group must be MET.

``offline_patterns`` (and ``offline_exclude``, which skips sentences such as
ones about relatives for personal-history criteria) are used only by the
offline extractor that powers the deterministic eval gate. Live LLM providers
never see them.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_HEADING = re.compile(r"^## +(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Criterion:
    id: str
    group: str
    text: str
    offline_patterns: tuple[str, ...] = ()
    offline_exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str          # e.g. "LAB-GEN-001#coverage-criteria"
    policy_id: str
    policy_version: str
    section: str
    text: str


@dataclass(frozen=True)
class Policy:
    id: str
    title: str
    version: str
    effective: str
    cpt_codes: tuple[str, ...]
    criteria: tuple[Criterion, ...]
    body: str
    chunks: tuple[PolicyChunk, ...] = field(default=())

    @property
    def groups(self) -> dict[str, list[Criterion]]:
        out: dict[str, list[Criterion]] = {}
        for c in self.criteria:
            out.setdefault(c.group, []).append(c)
        return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def parse_policy(text: str) -> Policy:
    m = _FRONT_MATTER.match(text)
    if not m:
        raise ValueError("policy is missing YAML front matter")
    meta = yaml.safe_load(m.group(1))
    body = m.group(2).strip()
    criteria = tuple(
        Criterion(
            id=c["id"],
            group=c["group"],
            text=c["text"],
            offline_patterns=tuple(c.get("offline_patterns", [])),
            offline_exclude=tuple(c.get("offline_exclude", [])),
        )
        for c in meta["criteria"]
    )
    ids = [c.id for c in criteria]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate criterion ids in {meta['id']}")
    version = str(meta["version"])
    chunks = []
    headings = list(_HEADING.finditer(body))
    for i, h in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        section = h.group(1).strip()
        section_text = body[h.end():end].strip()
        chunks.append(PolicyChunk(
            chunk_id=f"{meta['id']}#{_slug(section)}",
            policy_id=meta["id"],
            policy_version=version,
            section=section,
            text=f"{meta['title']} - {section}\n{section_text}",
        ))
    return Policy(
        id=meta["id"],
        title=meta["title"],
        version=version,
        effective=str(meta.get("effective", "")),
        cpt_codes=tuple(str(c) for c in meta["cpt_codes"]),
        criteria=criteria,
        body=body,
        chunks=tuple(chunks),
    )


def policy_dir() -> Path:
    return Path(os.environ.get("DXREVIEW_POLICY_DIR", Path(__file__).with_name("data")))


class PolicyStore:
    def __init__(self, policies: list[Policy]):
        self._by_id = {p.id: p for p in policies}
        self._by_cpt: dict[str, Policy] = {}
        for p in policies:
            for code in p.cpt_codes:
                if code in self._by_cpt:
                    raise ValueError(f"CPT {code} mapped to both {self._by_cpt[code].id} and {p.id}")
                self._by_cpt[code] = p

    @classmethod
    def from_dir(cls, path: Path | None = None) -> PolicyStore:
        path = path or policy_dir()
        return cls([parse_policy(f.read_text(encoding="utf-8")) for f in sorted(path.glob("*.md"))])

    def get(self, policy_id: str) -> Policy | None:
        return self._by_id.get(policy_id)

    def for_cpt(self, cpt_code: str) -> Policy | None:
        return self._by_cpt.get(cpt_code)

    def all(self) -> list[Policy]:
        return list(self._by_id.values())

    def chunks(self) -> list[PolicyChunk]:
        return [c for p in self._by_id.values() for c in p.chunks]


@lru_cache(maxsize=1)
def default_store() -> PolicyStore:
    return PolicyStore.from_dir()


__all__ = ["Criterion", "Policy", "PolicyChunk", "PolicyStore", "default_store", "parse_policy"]
