Candidate*\[Your Name\]*

RoleAI Engineer

Location*\[City, ST\]* · Remote

Email*\[you@email.com\]*

Code*\[github.com/you/dxreview\]*

AccessionDXR-2026-11

Portfolio · AI engineering for diagnostic test management

# Prior-auth review that approves with evidence and *never denies* on its own.

DxReview reads lab and genetic test orders against coverage policy. Claude extracts evidence from de-identified notes; deterministic code makes the call. Clear cases are approved with cited sentences, missing documentation is requested, and everything else goes to a clinician.

PythonRustGoTypeScript MCPRAG · pgvectorn8nKafka AWS Bedrock · ECS FargateHIPAA-aware

PANEL 01

## Run a review

Five synthetic orders, with output captured from the real pipeline. Pick one to see what the model saw, which steps ran, and why the case was routed the way it was.

Order

Clinical note as submittedPHI struck through

What the model receivedde-identified

Review graphms

PANEL 02

## Results against reference ranges

The CI eval gate runs 41 golden cases on every pull request. Safety metrics are zero-tolerance; quality metrics also can't drop more than two points against the saved baseline.

| Test | Result | Reference | Flag |
| --- | --- | --- | --- |
| Safety · hard gates |  |  |  |
| Unsafe approvals | 0 | = 0 | PASS |
| PHI spans in model payloads | 0 | = 0 | PASS |
| Injection cases ending in approval | 0 | = 0 | PASS |
| Quality |  |  |  |
| Decision accuracy (41 cases) | 97.6% | ≥ 90% | PASS |
| Criteria precision | 97.0% | ≥ 90% | PASS |
| Criteria recall | 100% | ≥ 80% | PASS |
| Evidence grounded verbatim | 100% | = 100% | PASS |
| Retrieval recall@3 | 100% | ≥ 90% | PASS |
| Copilot cites correct policy | 100% | ≥ 90% | PASS |
| Test suites |  |  |  |
| Python · TypeScript · Go · Rust | 72 · 6 · 6 · 3 | all green | PASS |

### How to read these numbers

CI runs a deterministic stand-in model, so the gate is free and reproducible. These results show that the pipeline, guardrails and decision logic are correct. Clinical reading quality comes from the same suite run against Claude on Bedrock, nightly and on every policy change.

The one miss is kept in the report on purpose. In "methylation testing was negative" the negation comes after the term, and the keyword stand-in can't parse that. It fails toward a clinician, which is the safe direction.

The evals also caught a real bug during development: delimiter neutralization ran before the injection scan and erased the markup the scan looks for. It's now a regression test.

PANEL 03

## Architecture

Each component uses the language that suits its job. Tool contracts, PHI test fixtures, policies and rules are shared files that every language reads, so the surfaces can't drift apart.

### Intake

**n8n intake workflow**webhook · validation · routing · PHI-safe errors

**Kafka worker**Go · idempotent · retries · DLQ

**MCP server**TypeScript · tools, policy resources, prompts

**n8n community node**TypeScript · three routed outputs

### Review graph · FastAPI on ECS Fargate

**Rules engine**YAML · frequency, lifetime, age, sex, dx

**De-identify**Rust scrubber · Comprehend Medical

**Injection scan**hits skip the model

**Hybrid retrieval**BM25 + vectors · RRF · pgvector

**Claude extracts criteria**forced tool call · temp 0 · cached system prompt

**Ground evidence**verbatim quotes only

**Decide in code**any / all logic · confidence floor

**Case memory**SQL · resubmissions · audit

Every step before the model can end the review early, so the cheapest correct answer wins. Any guardrail problem routes to a person, never to an approval.

### Outcomes

**APPROVE**→ UM system, with cited evidence

**NEEDS_INFO**→ provider portal, listing missing criteria

**CLINICAL_REVIEW**→ clinician queue, with flags and reasons

There is no DENY. Adverse determinations belong to clinicians.

PANEL 04

## Role requirements, with evidence

Each line of the AI Engineer description, matched to where it lives in the repository.

| Requirement | Evidence |
| --- | --- |
| Agentic systems: multi-step workflows, tool calling, MCP, RAG, memory | Review graph with early exits; bounded tool-use copilot; MCP server with tools, resources and prompts; hybrid RAG; SQL case memory across resubmissions`agent/pipeline.py` · `agent/copilot.py` · `mcp-server/` · `agent/memory.py` |
| Prompt and context engineering | Versioned, hashed prompt with changelog; schema-forced structured output; few-shot examples; extract → ground → decide chain; prompt caching`prompts/criteria_extraction.yaml` · `prompts/registry.py` |
| n8n workflow automation, self-hosting, custom nodes | Intake, error-handler and policy re-index workflows; community node built against current n8n types; self-hosted n8n on Postgres with PHI-safe retention`n8n/workflows/` · `n8n/custom-node/` · `infra/docker-compose.yml` |
| Evaluation, testing and observability | 41-case golden set with hard, min and regression gates; tracing with latency, tokens and cost; spans that refuse PHI attributes`evals/` · `observability.py` · `.github/workflows/` |
| Polyglot engineering (Python, Rust, Go, TypeScript) | Each language chosen per workload, with a written rationale`docs/adr/0005-polyglot-boundaries.md` |
| LLM APIs and SDKs (Anthropic, Bedrock) | Provider interface with Anthropic (forced tool use, retries, caching) and Bedrock Converse with Guardrails`llm/anthropic_provider.py` · `llm/bedrock_provider.py` |
| Docker, AWS ECS/Fargate, Kafka | Multi-stage images; Fargate services with autoscaling and circuit-breaker rollback; MSK consumer with at-least-once delivery and a DLQ`infra/terraform/` · `event-worker/` |
| Vector databases | pgvector HNSW with a generated tsvector column and RRF fusion in one SQL query`rag/store_pgvector.py` |
| Integration patterns (REST, webhooks, events) | FastAPI, n8n webhooks, Kafka topics, idempotency keys end to end`api.py` · `worker.go` |
| Rules engines with AI workflows | Declarative rules run before any model call; the model handles only what rules can't`policies/rules.yaml` · `rules/engine.py` |
| AI security and responsible AI | Injection screening, delimiter isolation, verbatim grounding, least-privilege tools, no automated denials; OWASP LLM Top 10 mapping`guardrails/` · `docs/hipaa-and-security.md` |
| HIPAA, PHI with AI vendors | De-identification plus a payload leak gate, Bedrock under the BAA, minimum-necessary prompts, KMS, no PHI in logs or n8n history`docs/adr/0003-phi-boundary-and-model-hosting.md` |
| Health plan operations | Utilization management, prior auth, CPT and ICD-10 pairing, frequency and lifetime limits, low-value testing, NEEDS_INFO resubmission loop |
| Code review, mentoring, documentation | Review checklist for prompts, agents and workflows; five ADRs; operations runbook`docs/review-checklist.md` · `docs/runbook.md` |

PANEL 05

## Decisions I'd defend in a design review

ADR-0001

### The model extracts; code decides

One narrow job for the LLM keeps approvals explainable down to a sentence, a policy version and a prompt hash. Even a model told to lie can't cause an approval.

ADR-0002

### Plain Python graph, n8n around it

Clinical logic lives in tested code. Business routing lives in n8n, where operations staff can see and change it.

ADR-0003

### De-identify even under a BAA

Minimum necessary as defense in depth. A leak detector blocks the call if any identifier survives.

ADR-0004

### Hybrid retrieval, structure-aware chunks

CPT codes and gene names need lexical match, paraphrased questions need vectors. RRF fuses both without calibration.

ADR-0005

### Contracts are data, not code

Tool schemas and PHI fixtures are shared files, so four languages stay in agreement.

PANEL 06

## Experience

*\[One or two sentences: years in software, years building with LLMs, and the domain you know best.\]*

*\[2022 – now\]*

### *\[Title\], \[Company\]*

- *\[Shipped X with LLMs/agents; measurable outcome, e.g. hours saved, cost per request\]*
- *\[Led or mentored: team size, what changed\]*
- *\[Platform work: AWS, Kafka, n8n, CI/CD\]*

*\[2018 – 2022\]*

### *\[Title\], \[Company\]*

- *\[Production system you owned end to end, with scale\]*
- *\[Integration or healthcare-adjacent work, if any\]*

*\[Earlier\]*

### *\[Title\], \[Company\]*

- *\[Foundation: languages, systems, Agile delivery\]*

### Languages

Python, Rust, Go, TypeScript/Node.js, Java/JVM, SQL

### AI

Anthropic, OpenAI, Azure OpenAI, AWS Bedrock; LangChain/LangGraph, LlamaIndex; MCP; RAG; evals

### Data and platform

pgvector, OpenSearch, Pinecone; Kafka; Docker; AWS EC2, ECS/Fargate; Terraform

### Automation and integration

n8n (self-hosted, custom nodes), Temporal, Airflow; REST, webhooks, SOAP/WSDL, SAML

DxReview uses synthetic data only. Policies are illustrative and are not clinical advice. Source: *\[github.com/you/dxreview\]*