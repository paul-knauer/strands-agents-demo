.PHONY: test test-unit test-eval lint typecheck check docker-build docker-run smoke

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit -v

test-eval:
	pytest tests/evaluation -m evaluation -v --no-cov

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	ruff check age_calculator/ scripts/

typecheck:
	mypy age_calculator/ --strict

check: lint typecheck test

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker build --target final -t age-calculator-agent:local .

docker-run:
	docker run --rm \
		-e MODEL_ARN=$(MODEL_ARN) \
		age-calculator-agent:local

# ── Scripts ───────────────────────────────────────────────────────────────────

smoke:
	python scripts/smoke_test.py --environment staging
