import pytest
from fastapi.testclient import TestClient

from dxreview.api import create_app
from dxreview.evals import run as evals

BODY = {"request_id": "r-1", "cpt_code": "82306", "note": "Osteoporosis on alendronate."}


@pytest.fixture
def client(graph, monkeypatch):
    monkeypatch.delenv("DXREVIEW_API_KEY", raising=False)
    return TestClient(create_app(graph=graph))


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok" and body["policies"] == 5 and body["prompt_version"]


def test_review_endpoint(client):
    r = client.post("/v1/reviews", json=BODY)
    assert r.status_code == 200 and r.json()["decision"] == "APPROVE"


def test_validation_error(client):
    assert client.post("/v1/reviews", json={**BODY, "cpt_code": "abc"}).status_code == 422


def test_idempotency_replay_and_conflict(client):
    h = {"Idempotency-Key": "k-1"}
    a = client.post("/v1/reviews", json=BODY, headers=h).json()
    b = client.post("/v1/reviews", json=BODY, headers=h).json()
    assert a == b
    c = client.post("/v1/reviews", json={**BODY, "note": "Fatigue."}, headers=h)
    assert c.status_code == 409


def test_api_key_required_when_configured(graph, monkeypatch):
    monkeypatch.setenv("DXREVIEW_API_KEY", "s3cret")
    c = TestClient(create_app(graph=graph))
    assert c.get("/v1/policies").status_code == 401
    assert c.get("/v1/policies", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.get("/healthz").status_code == 200


def test_policy_routes(client):
    assert len(client.get("/v1/policies").json()) == 5
    assert client.get("/v1/policies/LAB-GEN-005").json()["cpt_codes"] == ["81420", "81507"]
    assert client.get("/v1/policies/NOPE").status_code == 404


def test_copilot_route(client):
    r = client.post("/v1/copilot/ask", json={"question": "Are twin pregnancies eligible for cell-free DNA screening?"})
    assert r.json()["citations"][0]["chunk_id"] == "LAB-GEN-005#multiple-gestation"


def test_reindex_route(client):
    r = client.post("/v1/admin/reindex", json={"policy_ids": ["LAB-GEN-005"]})
    assert r.status_code == 200 and r.json()["reindexed_chunks"] > 0


def test_eval_gate_passes_offline():
    """The offline gate is part of the unit suite so CI fails on any regression."""
    assert evals.main(["--provider", "offline"]) == 0


def test_eval_gate_has_no_unsafe_approvals(graph):
    report = evals.run_review_evals(graph, evals.load_jsonl(evals.DATA / "review_cases.jsonl"))
    assert report["n"] == 41
    assert report["unsafe_approvals"] == 0 and report["phi_leaks"] == 0
    assert [m["id"] for m in report["misses"]] == ["neg-post-term-scope"]
