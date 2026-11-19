# DxReview

Agentic prior-authorization review for lab and genetic tests.

**The model extracts evidence. Code makes the decision.** Claude (through Bedrock or the Anthropic API) reads a de-identified clinical note and returns, for each coverage criterion, a status and a verbatim quote. Deterministic rules turn that evidence into one of three outcomes:

| Outcome | Meaning |
|---|---|
| `APPROVE` | Every criterion group is satisfied by verified, un-negated quotes |
| `NEEDS_INFO` | The note is silent on something the policy needs; the missing criteria are listed |
| `CLINICAL_REVIEW` | Anything else: contradiction, ambiguity, unverifiable quote, prompt injection, provider failure, unknown CPT code |

There is no automated `DENY`. An adverse determination has to come from a licensed clinician, every outcome is traceable to quotes and rule ids, and a model that cannot deny cannot be prompt-injected into denying.

> Author: [YOUR NAME] · [CONTACT] · [GITHUB] · [EXPERIENCE SUMMARY]

## Architecture

```
            n8n intake ──┐                    ┌── MCP server (TypeScript) ── agents / Claude
                         │                    │
 EHR / portal ─► Kafka ──┼─► Go worker ──► FastAPI (Python) ◄── n8n community node
   reviews.requests      │   at-least-once        │
                         │   idempotency, DLQ     ▼
                         │            ┌─ review graph ─────────────────────────────────┐
                         │            │ scrub PHI ─► scan injection ─► neutralize tags │
                         │            │ ─► load policy ─► hybrid RAG (BM25 + vectors,  │
                         │            │    RRF, pgvector) ─► Claude extracts evidence  │
                         │            │ ─► verify quotes + negation guard ─► decide    │
                         │            │ ─► audit (hashes, versions, counts; no PHI)    │
                         │            └────────────────────────────────────────────────┘
                         └─► reviews.results / reviews.dlq
 Rust phi-scrub CLI: same pattern table as the Python scrubber, parity-tested
 Terraform: ECS Fargate (private subnets, internal ALB), KMS, least-privilege Bedrock IAM
```

| Path | What |
|---|---|
| `python/dxreview/graph.py` | Review graph; every request ends in a decision, never a crash |
| `python/dxreview/decision.py` | Decision rules and the guards on MET evidence |
| `python/dxreview/phi/` | PHI scrubber (reference implementation) |
| `python/dxreview/safety.py` | Prompt-injection scan, then delimiter neutralization |
| `python/dxreview/rag/` | Tokenizer, BM25, embeddings (offline hashing / Titan), in-memory and pgvector stores, RRF |
| `python/dxreview/prompts/` | Versioned extraction prompt and tool schema (`extract-evidence/v3`) |
| `python/dxreview/providers/` | Anthropic, Bedrock (Converse), and the offline extractor used by the eval gate |
| `python/dxreview/copilot.py` | Policy Q&A that may only cite retrieved sections |
| `python/dxreview/api.py` | FastAPI: reviews (with `Idempotency-Key`), policies, copilot, re-index |
| `python/dxreview/evals/` | 41 review cases, 12 copilot questions, the CI gate |
| `shared/phi_patterns.json` | The single PHI pattern table used by Python and Rust |
| `rust/phi-scrubber/` | `phi-scrub` CLI and library; parity tests on shared fixtures |
| `go/worker/` | Kafka worker: commit after effects, idempotency keys, retries with jitter, DLQ |
| `ts/mcp-server/` | MCP tools (`review_prior_auth`, `ask_policy_copilot`, `list_policies`), `policy://` resources, two prompts |
| `ts/n8n-nodes-dxreview/` | n8n node with one output per decision |
| `n8n/workflows/` | Intake, error handler (PHI-safe alerts), policy re-index |
| `infra/terraform/` | ECS Fargate, KMS, ECR, Secrets Manager, scoped IAM |

## Quick start

```bash
cd python
pip install -e ".[dev]"
pytest -q                               # unit tests, including the offline eval gate
python -m dxreview.evals.run            # gate report
uvicorn dxreview.api:app --port 8080    # API with the offline provider

# Live model
export DXREVIEW_PROVIDER=anthropic ANTHROPIC_API_KEY=...
python -m dxreview.evals.run --provider anthropic
```

```bash
curl -s localhost:8080/v1/reviews -H 'content-type: application/json' -H 'Idempotency-Key: demo-1' -d '{
  "request_id": "demo-1", "cpt_code": "81162",
  "note": "Patient: Jane Roe, MRN 4471920. Diagnosed with breast cancer at age 41. Pre-test genetic counseling completed."
}'
```

Everything else: `make test`, or see `.github/workflows/ci.yml`. Full local stack: `docker compose up --build`.

## Eval gate (offline, deterministic)

| Metric | Gate | Result |
|---|---|---|
| Decision accuracy (41 cases) | ≥ 95% | **97.6%** (40/41) |
| Unsafe approvals | 0 | **0** |
| PHI leaks into results | 0 | **0** |
| Copilot citation hit rate (12 questions) | ≥ 90% | **91.7%** (11/12) |

The offline gate replaces the model with a rule-based extractor so CI can test everything around the model (scrubbing, injection handling, quote verification, decision rules) reproducibly. `--provider anthropic|bedrock` runs the same cases against the real model.

Tests: Python 100 (pytest, including parametrized cases), Rust 5, Go 9, TypeScript 10 (MCP 6, n8n 4).

## Design notes worth asking about

1. **The eval caught a real ordering bug.** Delimiter neutralization originally ran before the injection scan. Escaping `</clinical_note>` to `&lt;/clinical_note&gt;` erased exactly what the scan looks for, so delimiter-spoofing notes passed. The `inj-delimiter-spoof` case failed; `prepare_note` now scans first, and `test_scan_runs_before_neutralize` pins the order.
2. **The citation metric found a tokenizer bug.** `BRCA1/BRCA2` was one token, so a question about BRCA2 never matched the BRCA policy by keyword. Slashes now split; hyphenated terms emit parts and the joined form; light stemming joins *covered/coverage* and *documented/documentation*.
3. **The miss we kept on purpose.** Negation scope is not parsed. In "Mother diagnosed with ovarian cancer at 58, never tested", the cue sits after the term, so the criterion is AMBIGUOUS and the case goes to a clinician (`neg-post-term-scope`). It costs one case of accuracy and can never cause an unsafe approval.
4. **Why there is no DENY.** Regulations require clinician sign-off on adverse determinations; every automated outcome is auditable to quotes; and removing DENY from the output space removes the most damaging thing an injected note could ask for.

Other guards: quotes must appear verbatim in the note the model saw; a MET quote containing a negation cue, or with confidence below 0.7, is downgraded; injected notes never reach the model; the API never logs the note, only its scrubbed SHA-256; the Go worker and MCP server never echo API error bodies.

## Status

Verified in the build environment: Python tests and lint, eval gate, wheel install in a clean venv, API under uvicorn; Rust tests and clippy; Go vet and tests (the Kafka adapter type-checked against a stub of the kafka-go API); TypeScript builds and tests; Terraform parsed with an HCL parser.

Not yet run: `terraform validate`, Docker image builds, the Go worker against a real broker, pgvector against a live Postgres, live evals with an API key. CI runs the first two.

Before publishing, replace the bracketed placeholders in this README, `LICENSE`, and `ts/n8n-nodes-dxreview/credentials/DxReviewApi.credentials.ts`, and the `REPLACE_ME` credential ids in the n8n workflows after import.

## Policies

Five sample policies (`python/dxreview/policies/data/`): BRCA1/BRCA2 (LAB-GEN-001), Lynch syndrome (LAB-GEN-002), CYP2C19 for clopidogrel (LAB-PGX-003), 25-OH vitamin D (LAB-CHEM-004), cell-free DNA prenatal screening (LAB-GEN-005). They are illustrative and are not any payer's actual policy.
