# DxReview

**Agentic prior-authorization review for lab and genetic tests.**

The model extracts evidence. Code makes the decision.

Claude reads a de-identified clinical note and returns, for each coverage criterion, a status and a verbatim quote. Deterministic rules turn that evidence into one of three outcomes:

- **APPROVE**: every criterion is supported by a verified quote
- **NEEDS_INFO**: the note is missing something; the request lists exactly what
- **CLINICAL_REVIEW**: anything ambiguous, contradictory or suspicious goes to a clinician

There is no automated DENY. Adverse decisions belong to licensed clinicians, every outcome traces back to quotes and rules, and a model that cannot deny cannot be prompt-injected into denying.

## Results (offline eval gate)

| Metric | Result |
|---|---|
| Decision accuracy (41 cases) | 97.6% |
| Unsafe approvals | 0 |
| PHI leaks | 0 |
| Copilot citation accuracy | 91.7% |

## Stack

- **Python**: review pipeline, hybrid RAG (BM25 + vectors + pgvector), FastAPI, evals
- **Rust**: PHI scrubber, parity-tested against the Python version
- **Go**: Kafka worker with idempotency and a dead-letter queue
- **TypeScript**: MCP server and n8n community node
- **AWS**: Bedrock, ECS Fargate, KMS, least-privilege IAM (Terraform)

## Highlights

- **The evals caught a real bug.** The injection scan ran after delimiter escaping, which erased what it was looking for.
- **The copilot metric caught a tokenizer bug.** `BRCA1/BRCA2` was indexed as one word.
- **A known miss, kept on purpose.** Unclear negation goes to a clinician. It costs a little accuracy and never causes an unsafe approval.

## Quick start

```bash
cd python
pip install -e ".[dev]"
pytest -q
python -m dxreview.evals.run
uvicorn dxreview.api:app --port 8080
```

---

Ram Akhmitzyanov · arramzis@gmail · OK
