# DxReview portfolio: summary and interview talking points

**What it is:** an agentic prior-authorization reviewer for lab and genetic tests, built for the Avalon AI Engineer role. Portfolio page: https://claude.ai/artifact/EVjF48FpvNGEtJRvUTSCCW (private until shared). Repo delivered as dxreview.zip.

## Core thesis
The LLM (Claude via Bedrock or Anthropic) only extracts per-criterion evidence from a de-identified note, with verbatim quotes. Deterministic code makes the decision. Outcomes are APPROVE, NEEDS_INFO or CLINICAL_REVIEW. There is no automated DENY.

## Components
- Python: review graph, hybrid RAG (BM25 + vectors, RRF, pgvector), versioned prompt, Anthropic and Bedrock providers, policy copilot, FastAPI, evals
- Rust: PHI scrubber, parity-tested against Python with shared fixtures
- Go: Kafka worker (at-least-once delivery, idempotency keys, DLQ)
- TypeScript: MCP server (tools, policy resources, prompts) and an n8n community node
- n8n: intake, error handler and policy re-index workflows
- Terraform: ECS Fargate, KMS, least-privilege Bedrock IAM

## Numbers (offline eval gate)
97.6% decision accuracy on 41 cases. 0 unsafe approvals. 0 PHI leaks. Tests: 72 Python, 6 TS, 6 Go, 3 Rust.

## Stories for interviews
1. The eval caught a real bug: delimiter neutralization ran before the injection scan and erased what the scan looks for.
2. A tokenization bug (BRCA1/BRCA2 kept as one token) was found by the copilot citation metric.
3. The miss we kept on purpose: a negation after the term fails toward a clinician.
4. Why there is no DENY: regulations, auditability, and resistance to prompt injection.

## Still to do (owner)
- Replace the bracketed placeholders (name, contact, GitHub, experience) on the page and in the LICENSE and the n8n credential URL.
- Push to GitHub, run CI (Docker builds and terraform validate haven't been run yet), and run the live evals with an API key.
