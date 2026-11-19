import json
from pathlib import Path

import pytest

from dxreview import phi

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads((ROOT / "shared" / "fixtures" / "phi_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", FIXTURES, ids=[c["name"] for c in FIXTURES])
def test_shared_fixture(case):
    """Same fixtures as rust/phi-scrubber/tests/parity.rs."""
    r = phi.scrub(case["input"])
    assert r.text == case["expected"]
    assert dict(sorted(r.counts.items())) == case["counts"]


def test_bundled_patterns_match_shared_source():
    bundled = Path(phi.__file__).with_name("patterns.json").read_text()
    shared = (ROOT / "shared" / "phi_patterns.json").read_text()
    assert bundled == shared, "run `make sync-patterns`"


def test_scrub_is_idempotent():
    once = phi.scrub("Pt: Ana Diaz, MRN 99887766, call 555-123-4567").text
    assert phi.scrub(once).text == once


def test_clinical_codes_survive():
    text = "CPT 81162, ICD-10 Z80.3, CYP2C19*2, MSI-H, eGFR 22"
    assert phi.scrub(text).text == text
