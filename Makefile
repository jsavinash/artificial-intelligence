# ============================================================================
# ML Platform — Supervised Regression Monorepo
# All operations via uv (https://docs.astral.sh/uv/). Run `make help`.
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# --- Configuration ----------------------------------------------------------
PORT            ?= 8000
ALPHA           ?= 1.0
MIN_R2          ?= 0.40
TRACKING_URI    ?= http://localhost:5000
ARTIFACTS_DIR   ?= artifacts
MODEL_PATH      ?= $(ARTIFACTS_DIR)/latest/pipeline.skops
IMAGE           ?= ml-platform/api:local
UV_FLAGS        :=

# --- Primary targets --------------------------------------------------------

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: check
check: lint format-check typecheck test ## Run all quality gates (CI parity, minus docker)

.PHONY: ci
ci: check docker-build ## Run everything CI runs, including the image build

.PHONY: all
all: install train export serve-demo ## Install, train, export, and boot the API

# --- Environment ------------------------------------------------------------

.PHONY: install
install: ## Sync all workspace packages (frozen lockfile)
	uv sync --all-packages $(UV_FLAGS)

.PHONY: install-frozen
install-frozen: ## Sync strictly from uv.lock (no resolution)
	uv sync --frozen --all-packages

.PHONY: lock
lock: ## Re-resolve and rewrite uv.lock
	uv lock

.PHONY: upgrade
upgrade: ## Upgrade all dependencies and refresh the lockfile
	uv lock --upgrade && uv sync --all-packages

# --- Quality gates ----------------------------------------------------------

.PHONY: lint
lint: ## Ruff lint
	uv run ruff check .

.PHONY: format
format: ## Ruff format (rewrite files)
	uv run ruff format .

.PHONY: format-check
format-check: ## Ruff format (verify only)
	uv run ruff format --check .

.PHONY: typecheck
typecheck: ## mypy strict over libs and apps
	uv run mypy libs apps

.PHONY: test
test: ## Run test suite (warnings are errors)
	uv run pytest

.PHONY: test-cov
test-cov: ## Run test suite with coverage report
	uv run pytest --cov --cov-report=term-missing

.PHONY: audit
audit: ## Dependency vulnerability scan (pip-audit)
	uv tool run pip-audit --skip-editable

# --- Model lifecycle --------------------------------------------------------

.PHONY: train
train: ## Train with MLflow tracking (ALPHA=1.0 TRACKING_URI=... MIN_R2=0.40)
	uv run --package pipelines python -m pipelines.train \
		--alpha $(ALPHA) --min-r2 $(MIN_R2) --tracking-uri $(TRACKING_URI)

.PHONY: train-local
train-local: ## Train with fallback to local sqlite (no MLflow server needed)
	uv run --package pipelines python -m pipelines.train \
		--alpha $(ALPHA) --min-r2 $(MIN_R2) \
		--allow-fallback --tracking-uri $(TRACKING_URI)

.PHONY: export
export: ## Export + sign latest artifact and promote artifacts/latest
	uv run --package pipelines python -m pipelines.export \
		--tracking-uri $(TRACKING_URI) --out $(ARTIFACTS_DIR)

.PHONY: serve
serve: ## Run the API locally (PORT=8000, MODEL_PATH=artifacts/latest/pipeline.skops)
	MODEL_ARTIFACT_PATH=$(MODEL_PATH) \
		uv run --package api uvicorn api.main:app --host 127.0.0.1 --port $(PORT) --reload

.PHONY: serve-prod
serve-prod: ## Run the API with production settings (2 workers, no reload)
	MODEL_ARTIFACT_PATH=$(MODEL_PATH) \
		uv run --package api uvicorn api.main:app --host 0.0.0.0 --port $(PORT) --workers 2 --no-access-log

# --- Smoke tests ------------------------------------------------------------

.PHONY: smoke
smoke: ## Hit /ready, /predict, and /metrics on a running API (PORT=8000)
	@curl -fsS http://127.0.0.1:$(PORT)/ready > /dev/null || { echo "API not ready on :$(PORT)"; exit 1; }
	@echo "ready:  OK"
	@curl -fsS -X POST http://127.0.0.1:$(PORT)/predict \
		-H 'Content-Type: application/json' \
		-d '{"records":[{"med_inc":8.3,"house_age":41.0,"avg_occupancy":6.98}]}' \
		| grep -q '"count":1' && echo "predict: OK"
	@curl -fsS http://127.0.0.1:$(PORT)/metrics | grep -q model_predictions_total \
		&& echo "metrics: OK"

# --- Docker -----------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build the multi-stage serving image (IMAGE=ml-platform/api:local)
	docker build -f infrastructure/Dockerfile -t $(IMAGE) .

.PHONY: docker-run
docker-run: ## Run the serving container (expects artifacts/ present)
	docker run -d --name ml-platform-api -p $(PORT):8000 \
		-v "$(CURDIR)/$(ARTIFACTS_DIR):/models:ro" \
		-e MODEL_ARTIFACT_PATH=/models/latest/pipeline.skops \
		$(IMAGE)

.PHONY: docker-stop
docker-stop: ## Stop and remove the serving container
	docker rm -f ml-platform-api 2>/dev/null || true

.PHONY: stack-up
stack-up: ## Start local stack: API + MLflow + Prometheus
	cd infrastructure && docker compose up --build -d

.PHONY: stack-down
stack-down: ## Stop the local stack (keep volumes)
	cd infrastructure && docker compose down

.PHONY: stack-nuke
stack-nuke: ## Stop the local stack and delete volumes (destroys MLflow data)
	cd infrastructure && docker compose down -v

.PHONY: stack-logs
stack-logs: ## Tail local-stack logs
	cd infrastructure && docker compose logs -f

# --- Cleanup ----------------------------------------------------------------

.PHONY: clean
clean: ## Remove caches, build outputs, and local tracking DBs
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov \
		**/__pycache__ */**/__pycache__ 2>/dev/null || true
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-artifacts
clean-artifacts: ## Remove exported model artifacts
	rm -rf $(ARTIFACTS_DIR)

.PHONY: clean-all
clean-all: clean clean-artifacts ## Remove caches AND model artifacts
