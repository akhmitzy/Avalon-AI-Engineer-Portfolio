"""HTTP API.

Run: ``uvicorn dxreview.api:app --host 0.0.0.0 --port 8080``

Auth: when DXREVIEW_API_KEY is set, every /v1 route requires ``X-API-Key``.
Idempotency: POST /v1/reviews honours ``Idempotency-Key``. Replaying a key
with the same body returns the stored result; with a different body, 409.
The raw note is never logged or stored; only its scrubbed hash is.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
from collections import OrderedDict

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .copilot import PolicyCopilot
from .graph import ReviewGraph
from .models import CopilotAnswer, ReviewRequest, ReviewResult
from .prompts import PROMPT_VERSION, prompt_fingerprint


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    policy_id: str | None = None


class ReindexRequest(BaseModel):
    policy_ids: list[str] | None = None


class _IdempotencyCache:
    """Bounded in-process cache. Production deployments put this in Redis or Postgres."""

    def __init__(self, max_items: int = 10_000):
        self._d: OrderedDict[str, tuple[str, ReviewResult]] = OrderedDict()
        self._lock = threading.Lock()
        self.max_items = max_items

    def get(self, key: str):
        with self._lock:
            return self._d.get(key)

    def put(self, key: str, body_hash: str, result: ReviewResult) -> None:
        with self._lock:
            self._d[key] = (body_hash, result)
            self._d.move_to_end(key)
            while len(self._d) > self.max_items:
                self._d.popitem(last=False)


def create_app(graph: ReviewGraph | None = None, copilot: PolicyCopilot | None = None) -> FastAPI:
    graph = graph or ReviewGraph()
    copilot = copilot or PolicyCopilot(graph.retriever)
    cache = _IdempotencyCache()
    app = FastAPI(title="DxReview", version=__version__,
                  description="Prior-authorization evidence review. Outcomes: APPROVE, NEEDS_INFO, CLINICAL_REVIEW.")

    def require_key(x_api_key: str | None = Header(default=None)) -> None:
        expected = os.environ.get("DXREVIEW_API_KEY")
        if expected and not (x_api_key and hmac.compare_digest(x_api_key, expected)):
            raise HTTPException(status_code=401, detail="invalid or missing API key")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": __version__, "prompt_version": PROMPT_VERSION,
                "prompt_fingerprint": prompt_fingerprint(), "model": graph.extractor.model_id,
                "policies": len(graph.store.all())}

    @app.get("/v1/policies", dependencies=[Depends(require_key)])
    def list_policies():
        return [{"id": p.id, "title": p.title, "version": p.version, "cpt_codes": list(p.cpt_codes),
                 "criteria": [{"id": c.id, "group": c.group, "text": c.text} for c in p.criteria]}
                for p in graph.store.all()]

    @app.get("/v1/policies/{policy_id}", dependencies=[Depends(require_key)])
    def get_policy(policy_id: str):
        p = graph.store.get(policy_id)
        if p is None:
            raise HTTPException(status_code=404, detail="policy not found")
        return {"id": p.id, "title": p.title, "version": p.version, "effective": p.effective,
                "cpt_codes": list(p.cpt_codes), "body": p.body,
                "criteria": [{"id": c.id, "group": c.group, "text": c.text} for c in p.criteria]}

    @app.post("/v1/reviews", response_model=ReviewResult, dependencies=[Depends(require_key)])
    def create_review(req: ReviewRequest, idempotency_key: str | None = Header(default=None)):
        body_hash = hashlib.sha256(req.model_dump_json().encode()).hexdigest()
        if idempotency_key:
            hit = cache.get(idempotency_key)
            if hit:
                if hit[0] != body_hash:
                    raise HTTPException(status_code=409, detail="Idempotency-Key reused with a different body")
                return hit[1]
        result = graph.run(req)
        if idempotency_key:
            cache.put(idempotency_key, body_hash, result)
        return result

    @app.post("/v1/copilot/ask", response_model=CopilotAnswer, dependencies=[Depends(require_key)])
    def ask(req: AskRequest):
        return copilot.ask(req.question, policy_id=req.policy_id)

    @app.post("/v1/admin/reindex", dependencies=[Depends(require_key)])
    def reindex(req: ReindexRequest):
        from .policies import PolicyStore
        graph.store = PolicyStore.from_dir()
        graph.retriever.store = graph.store
        n = graph.retriever.reindex(req.policy_ids)
        return {"reindexed_chunks": n, "policies": [p.id for p in graph.store.all()]}

    return app


def __getattr__(name: str):
    # Lazily build the module-level app so importing dxreview.api in tests is cheap.
    if name == "app":
        global app
        app = create_app()
        return app
    raise AttributeError(name)
