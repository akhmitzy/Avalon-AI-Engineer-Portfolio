.PHONY: test test-python test-rust test-go test-ts evals sync-patterns fixtures run

test: test-python test-rust test-go test-ts

test-python:
	cd python && ruff check . && pytest -q

evals:
	cd python && python -m dxreview.evals.run

evals-live:
	cd python && python -m dxreview.evals.run --provider $${PROVIDER:-anthropic}

test-rust:
	cd rust/phi-scrubber && cargo test

test-go:
	cd go/worker && go vet ./internal/... && go test ./internal/...

test-ts:
	cd ts/mcp-server && npm ci && npm test
	cd ts/n8n-nodes-dxreview && npm ci && npm test

# The Python package bundles a copy of the shared pattern table (tests fail if they differ).
sync-patterns:
	cp shared/phi_patterns.json python/dxreview/phi/patterns.json

run:
	cd python && uvicorn dxreview.api:app --reload --port 8080
