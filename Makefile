.PHONY: help install sync dev test test-cov test-fast lint format format-check check build clean clean-all ci

BLUE := \033[0;34m
GREEN := \033[0;32m
NC := \033[0m

help:
	@echo "$(BLUE)nuverse$(NC)"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  make install         Install uv if needed"
	@echo "  make sync            Sync workspace"
	@echo "  make dev             Full dev setup (sync + pre-commit)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make test            Run all tests"
	@echo "  make test-cov        Run tests with coverage"
	@echo "  make test-fast       Run tests (fail fast)"
	@echo ""
	@echo "$(GREEN)Code quality:$(NC)"
	@echo "  make lint            Check code with ruff"
	@echo "  make format          Format code with ruff"
	@echo "  make check           Run format-check + lint"
	@echo ""
	@echo "$(GREEN)Packages:$(NC)"
	@echo "  make build PKG=<dist> Build one wheel, eg PKG=nuverse-demos"
	@echo ""
	@echo "$(GREEN)Cleanup:$(NC)"
	@echo "  make clean           Remove build artifacts"
	@echo "  make clean-all       Remove everything including .venv"

install:
	@command -v uv >/dev/null 2>&1 || { \
		echo "$(BLUE)Installing uv...$(NC)"; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	}
	@echo "$(GREEN)uv ready$(NC)"

sync: install
	uv sync --all-packages

dev: sync
	uv run pre-commit install

test:
	uv run pytest

test-cov:
	uv run pytest --cov --cov-report=html --cov-report=term-missing

test-fast:
	uv run pytest -x

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

format-check:
	uv run ruff format --check .

check: format-check lint
	@echo "$(GREEN)All checks passed$(NC)"

build:
	@test -n "$(PKG)" || { echo "PKG=<dist> is required, eg PKG=nuverse"; exit 1; }
	cd pkgs/$(PKG) && uv build --wheel --out-dir dist

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ reports/

clean-all: clean
	rm -rf .venv/

ci: check test-cov
	@echo "$(GREEN)CI passed$(NC)"
