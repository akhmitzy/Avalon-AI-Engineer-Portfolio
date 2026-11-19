import pytest

from dxreview.decision import apply_guards, decide, verify_quote
from dxreview.models import CriterionEvidence as Ev
from dxreview.models import Decision
from dxreview.models import EvidenceStatus as S

NOTE = "Genetic counseling completed. Diagnosed with breast cancer at age 41. Mother had ovarian cancer, not tested."


@pytest.fixture
def brca(store):
    return store.get("LAB-GEN-001")


def run(policy, evidence, note=NOTE, flags=()):
    results = apply_guards(policy, evidence, note)
    return decide(policy, results, list(flags))


def test_approve_when_required_and_one_history_met(brca):
    d, _, _ = run(brca, [
        Ev(criterion_id="genetic_counseling", status=S.MET, quote="Genetic counseling completed."),
        Ev(criterion_id="personal_early_breast_cancer", status=S.MET, quote="Diagnosed with breast cancer at age 41."),
    ])
    assert d == Decision.APPROVE


def test_missing_required_is_needs_info(brca):
    d, _, missing = run(brca, [
        Ev(criterion_id="personal_early_breast_cancer", status=S.MET, quote="Diagnosed with breast cancer at age 41."),
    ])
    assert d == Decision.NEEDS_INFO and missing == ["genetic_counseling"]


def test_missing_whole_group_lists_all_options(brca):
    d, _, missing = run(brca, [Ev(criterion_id="genetic_counseling", status=S.MET, quote="Genetic counseling completed.")])
    assert d == Decision.NEEDS_INFO
    assert set(missing) == {"personal_early_breast_cancer", "personal_ovarian_pancreatic_cancer", "family_history"}


def test_not_met_required_goes_to_clinician_never_deny(brca):
    d, _, _ = run(brca, [Ev(criterion_id="genetic_counseling", status=S.NOT_MET, quote="Genetic counseling completed.")])
    assert d == Decision.CLINICAL_REVIEW
    assert "DENY" not in Decision.__members__


def test_hallucinated_quote_downgraded(brca):
    d, reasons, _ = run(brca, [
        Ev(criterion_id="genetic_counseling", status=S.MET, quote="Counseling with a geneticist on Monday."),
        Ev(criterion_id="personal_early_breast_cancer", status=S.MET, quote="Diagnosed with breast cancer at age 41."),
    ])
    assert d == Decision.CLINICAL_REVIEW and "genetic_counseling:ambiguous" in reasons


def test_negation_in_met_quote_downgraded(brca):
    results = apply_guards(brca, [
        Ev(criterion_id="genetic_counseling", status=S.MET, quote="Genetic counseling completed."),
        Ev(criterion_id="family_history", status=S.MET, quote="Mother had ovarian cancer, not tested."),
    ], NOTE)
    fam = next(r for r in results if r.criterion_id == "family_history")
    assert fam.status == S.AMBIGUOUS and "negation_in_quote" in fam.notes


def test_low_confidence_downgraded(brca):
    results = apply_guards(brca, [Ev(criterion_id="genetic_counseling", status=S.MET,
                                     quote="Genetic counseling completed.", confidence=0.4)], NOTE)
    assert results[0].status == S.AMBIGUOUS and "low_confidence" in results[0].notes


def test_met_in_group_outweighs_ambiguous_sibling(brca):
    d, _, _ = run(brca, [
        Ev(criterion_id="genetic_counseling", status=S.MET, quote="Genetic counseling completed."),
        Ev(criterion_id="personal_early_breast_cancer", status=S.MET, quote="Diagnosed with breast cancer at age 41."),
        Ev(criterion_id="family_history", status=S.AMBIGUOUS, quote="Mother had ovarian cancer, not tested."),
    ])
    assert d == Decision.APPROVE


def test_flags_force_clinical_review(brca):
    d, reasons, _ = run(brca, [
        Ev(criterion_id="genetic_counseling", status=S.MET, quote="Genetic counseling completed."),
        Ev(criterion_id="personal_early_breast_cancer", status=S.MET, quote="Diagnosed with breast cancer at age 41."),
    ], flags=["prompt_injection:delimiter_spoof"])
    assert d == Decision.CLINICAL_REVIEW and reasons == ["safety_flag:prompt_injection:delimiter_spoof"]


def test_review_outranks_needs_info(brca):
    d, _, missing = run(brca, [Ev(criterion_id="family_history", status=S.AMBIGUOUS, quote="Mother had ovarian cancer, not tested.")])
    assert d == Decision.CLINICAL_REVIEW and "genetic_counseling" in missing


@pytest.mark.parametrize("quote,ok", [
    ("Genetic counseling completed.", True),
    ("genetic   counseling\ncompleted.", True),
    ("Genetic counseling was completed.", False),
    ("", False),
    ("abc", False),
])
def test_verify_quote(quote, ok):
    assert verify_quote(quote, NOTE) is ok
