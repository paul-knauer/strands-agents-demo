# ── Testing ───────────────────────────────────────────────────────────────────

.PHONY: test
test:
	pytest tests/ -v

.PHONY: test-unit
test-unit:
	pytest tests/unit -v

.PHONY: test-eval
test-eval:
	pytest tests/evaluation -m evaluation -v --no-cov

# ── Code quality ──────────────────────────────────────────────────────────────

.PHONY: lint
lint:
	ruff check age_calculator/ scripts/

.PHONY: typecheck
typecheck:
	mypy age_calculator/ --strict

.PHONY: check
check: lint typecheck test

# ── Docker ────────────────────────────────────────────────────────────────────

.PHONY: docker-build
docker-build:
	docker build --target final -t age-calculator-agent:local .

.PHONY: docker-run
docker-run:
	docker run --rm \
		-e MODEL_ARN=$(MODEL_ARN) \
		age-calculator-agent:local

# ── Scripts ───────────────────────────────────────────────────────────────────

.PHONY: smoke
smoke:
	python scripts/smoke_test.py --environment staging
