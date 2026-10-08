.PHONY: help setup test lint format check demo evals api up down clean

PYTHON ?= python
UV ?= uv

help:
	@echo "Surface-Aware Agent Orchestration Development Commands"
	@echo ""
	@echo "  make setup    Install all workspace packages and development tooling via uv"
	@echo "  make test     Run the full test suite with pytest"
	@echo "  make lint     Run ruff linter and mypy type checks"
	@echo "  make format   Format codebase with ruff"
	@echo "  make check    Run formatting, linting, and tests"
	@echo "  make demo     Launch the interactive CLI demo REPL"
	@echo "  make evals    Run the routing evaluation harness against configured router"
	@echo "  make api      Start the FastAPI HTTP ingress service on port 8000"
	@echo "  make up       Start Postgres+pgvector docker container (optional)"
	@echo "  make down     Stop docker containers (optional)"
	@echo "  make clean    Remove caches and temporary artifacts"

setup:
	$(UV) sync --all-packages

test:
	$(UV) run pytest -v

lint:
	$(UV) run ruff check .
	$(UV) run mypy .

format:
	$(UV) run ruff format .

check: lint test

demo:
	$(UV) run $(PYTHON) -m orchestrator.cli_entry

evals:
	$(UV) run $(PYTHON) -m evals.runner

api:
	$(UV) run uvicorn api.main:app --reload --port 8000

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
