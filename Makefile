.PHONY: install install-benchmark download-models test test-all test-agent test-proxy lint sweep bench bench-external bench-external-public bench-external-local clean run run-guarded

# ── Install ──────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

install-benchmark:
	pip install -e ".[benchmark]"

# ── Model downloads ───────────────────────────────────────────────────────────
download-models:
	python download_models.py
	python -m spacy download en_core_web_trf
	python -m spacy download en_core_web_sm

# ── Testing ───────────────────────────────────────────────────────────────────
## Fast: unit + property-based tests (ML models mocked — no download needed)
test:
	pytest tests/ -m "not integration" -v --tb=short

## Full: includes end-to-end tests with real models (requires download-models first)
test-all:
	pytest tests/ -v --tb=short

## Integration tests only (real models)
test-integration:
	pytest tests/test_integration.py -m integration -v --tb=short

## Agent loop integration tests (real models, simulated agentic workflows)
test-agent:
	pytest tests/test_agent_loop.py -m integration -v --tb=short

## Proxy middleware unit tests (mocked models — fast)
test-proxy:
	pytest tests/test_proxy.py -v --tb=short

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	ruff check server/ benchmarks/ tests/
	ruff format --check server/ benchmarks/ tests/

# ── Benchmark & calibration ───────────────────────────────────────────────────
## Run MCPEvol-Bench evaluation harness (produces benchmarks/results.json)
bench:
	python benchmarks/mcpevol_runner.py \
		--dataset benchmarks/mcpevol.json \
		--output benchmarks/results.json \
		--verbose

## Run external grounded fact-checking evaluation (entailment component only)
bench-external:
	python benchmarks/external_eval.py \
		--output benchmarks/external_results.json \
		--verbose

## Run the public LLM-AggreFact test split; HF access approval may be required.
bench-external-public:
	python benchmarks/external_eval.py \
		--source hf \
		--split test \
		--output benchmarks/aggrefact_results.json \
		--verbose

## Run against manually downloaded LLM-AggreFact parquet shards.
bench-external-local:
	python benchmarks/external_eval.py \
		--source local \
		--local-dir . \
		--split test \
		--output benchmarks/aggrefact_local_results.json \
		--verbose

## GED threshold sweep (reports best threshold for configs/thresholds.yaml)
sweep:
	python benchmarks/threshold_sweep.py --dataset benchmarks/mcpevol.json

# ── Dev servers ───────────────────────────────────────────────────────────────
## Standard server (agent calls verify_* tools explicitly)
run:
	python server/main.py

## Guarded server (proxy interception — automatic pre-execution verification)
run-guarded:
	python server/main_guarded.py

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
