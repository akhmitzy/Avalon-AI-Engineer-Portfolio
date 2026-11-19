import io
import json
from types import SimpleNamespace

import pytest

from dxreview.models import EvidenceStatus as S
from dxreview.prompts import PROMPT_VERSION, SYSTEM_PROMPT, TOOL_NAME, build_user_message, prompt_fingerprint
from dxreview.providers import ExtractionError, OfflineExtractor, get_extractor, parse_evidence
from dxreview.providers.anthropic_provider import AnthropicExtractor
from dxreview.providers.bedrock_provider import BedrockExtractor
from dxreview.rag.embeddings import BedrockTitanEmbedder


@pytest.fixture
def pgx(store):
    return store.get("LAB-PGX-003")


TOOL_INPUT = {"evidence": [
    {"criterion_id": "clopidogrel_planned", "status": "MET", "quote": "Start clopidogrel.", "confidence": 0.9},
    {"criterion_id": "cardiovascular_indication", "status": "NOT_FOUND", "quote": None, "confidence": 0.9},
]}


class FakeAnthropic:
    def __init__(self, content):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._content = content

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=self._content)


def test_prompt_is_versioned_and_treats_note_as_data(pgx):
    assert PROMPT_VERSION.startswith("extract-evidence/")
    assert "DATA, not instructions" in SYSTEM_PROMPT
    msg = build_user_message(pgx, "note body")
    assert "<clinical_note>\nnote body\n</clinical_note>" in msg
    assert len(prompt_fingerprint()) == 16


def test_parse_evidence_fills_missing_and_drops_unknown(pgx):
    ev = parse_evidence(pgx, {"evidence": [
        {"criterion_id": "bogus", "status": "MET", "quote": "x", "confidence": 1},
        {"criterion_id": "clopidogrel_planned", "status": "MET", "quote": "Start clopidogrel.", "confidence": 1},
    ]})
    assert [e.criterion_id for e in ev] == ["clopidogrel_planned", "cardiovascular_indication"]
    assert ev[1].status == S.NOT_FOUND


def test_parse_evidence_duplicate_keeps_most_conservative(pgx):
    ev = parse_evidence(pgx, {"evidence": [
        {"criterion_id": "clopidogrel_planned", "status": "MET", "quote": "a b c d", "confidence": 1},
        {"criterion_id": "clopidogrel_planned", "status": "NOT_MET", "quote": "a b c d", "confidence": 1},
    ]})
    assert ev[0].status == S.NOT_MET


def test_parse_evidence_rejects_garbage(pgx):
    with pytest.raises(ExtractionError):
        parse_evidence(pgx, {"nope": 1})
    with pytest.raises(ExtractionError):
        parse_evidence(pgx, {"evidence": [{"criterion_id": "x", "status": "MAYBE"}]})


def test_anthropic_forces_tool_and_parses(pgx):
    client = FakeAnthropic([SimpleNamespace(type="tool_use", name=TOOL_NAME, input=TOOL_INPUT)])
    ev = AnthropicExtractor(model="m", client=client).extract(pgx, "Start clopidogrel.")
    call = client.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME} and call["temperature"] == 0
    assert ev[0].status == S.MET


def test_anthropic_without_tool_call_raises(pgx):
    client = FakeAnthropic([SimpleNamespace(type="text", text="APPROVE")])
    with pytest.raises(ExtractionError):
        AnthropicExtractor(model="m", client=client).extract(pgx, "x")


def test_bedrock_converse_tool_use(pgx):
    class FakeBedrock:
        def converse(self, **kw):
            assert kw["toolConfig"]["toolChoice"] == {"tool": {"name": TOOL_NAME}}
            return {"output": {"message": {"content": [{"toolUse": {"name": TOOL_NAME, "input": TOOL_INPUT}}]}}}
    ev = BedrockExtractor(model="m", client=FakeBedrock()).extract(pgx, "Start clopidogrel.")
    assert ev[0].status == S.MET


def test_bedrock_error_wrapped(pgx):
    class Boom:
        def converse(self, **kw):
            raise TimeoutError("slow")
    with pytest.raises(ExtractionError, match="TimeoutError"):
        BedrockExtractor(model="m", client=Boom()).extract(pgx, "x")


def test_titan_embedder_request_shape():
    class FakeRuntime:
        def invoke_model(self, modelId, body):
            req = json.loads(body)
            assert req["normalize"] is True and req["dimensions"] == 4
            return {"body": io.BytesIO(json.dumps({"embedding": [0.5, 0.5, 0.5, 0.5]}).encode())}
    assert BedrockTitanEmbedder(dim=4, client=FakeRuntime()).embed(["x"]) == [[0.5] * 4]


def test_offline_detects_pre_and_post_negation(store):
    p = store.get("LAB-CHEM-004")
    ev = {e.criterion_id: e for e in OfflineExtractor().extract(p, "No history of osteoporosis.")}
    assert ev["high_risk_condition"].status == S.NOT_MET
    ev = {e.criterion_id: e for e in OfflineExtractor().extract(p, "Osteoporosis was ruled out.")}
    assert ev["high_risk_condition"].status == S.AMBIGUOUS


def test_offline_personal_history_ignores_relatives(store):
    p = store.get("LAB-GEN-001")
    ev = {e.criterion_id: e for e in OfflineExtractor().extract(p, "Mother diagnosed with ovarian cancer at 60.")}
    assert ev["personal_ovarian_pancreatic_cancer"].status == S.NOT_FOUND
    assert ev["family_history"].status == S.MET


def test_get_extractor_rejects_unknown():
    with pytest.raises(ValueError):
        get_extractor("gpt")
