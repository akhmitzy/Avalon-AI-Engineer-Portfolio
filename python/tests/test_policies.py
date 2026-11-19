import pytest

from dxreview.policies import PolicyStore, parse_policy

MINIMAL = """---
id: T-1
title: Test
version: "1"
cpt_codes: ["99999"]
criteria:
  - id: a
    group: required
    text: A
---
## Coverage criteria
Covered when A.
"""


def test_all_policies_load(store):
    assert {p.id for p in store.all()} == {"LAB-GEN-001", "LAB-GEN-002", "LAB-PGX-003", "LAB-CHEM-004", "LAB-GEN-005"}


def test_cpt_lookup(store):
    assert store.for_cpt("81162").id == "LAB-GEN-001"
    assert store.for_cpt("00000") is None


def test_every_policy_has_coverage_section(store):
    for p in store.all():
        assert any(c.section == "Coverage criteria" for c in p.chunks), p.id


def test_every_criterion_has_offline_patterns(store):
    for p in store.all():
        for c in p.criteria:
            assert c.offline_patterns, f"{p.id}:{c.id}"


def test_parse_minimal():
    p = parse_policy(MINIMAL)
    assert p.id == "T-1" and p.chunks[0].chunk_id == "T-1#coverage-criteria"


def test_missing_front_matter_rejected():
    with pytest.raises(ValueError):
        parse_policy("## no front matter")


def test_duplicate_cpt_rejected():
    p = parse_policy(MINIMAL)
    q = parse_policy(MINIMAL.replace("T-1", "T-2"))
    with pytest.raises(ValueError, match="CPT 99999"):
        PolicyStore([p, q])
