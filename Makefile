# Swiggy Nexus — Development Makefile
# ──────────────────────────────────────────────────────────────────────────────
# Targets: dev | test | lint | clean | install | help

.PHONY: dev backend frontend test lint lint-py lint-js clean install help

# ──────────────────────────────────────────────────────────────────────────────
# Help (default)
# ──────────────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Swiggy Nexus — make targets"
	@echo ""
	@echo "  make dev        Start both backend (uvicorn) and frontend (Next.js)"
	@echo "  make backend    Start only the FastAPI backend on :8000"
	@echo "  make frontend   Start only the Next.js frontend on :3000"
	@echo "  make test       Run all pytest tests"
	@echo "  make lint       Run ruff (Python) and eslint (JS)"
	@echo "  make lint-py    Run ruff only"
	@echo "  make lint-js    Run eslint only"
	@echo "  make install    Install Python + Node deps"
	@echo "  make clean      Remove build artefacts and caches"
	@echo ""

# ──────────────────────────────────────────────────────────────────────────────
# Install
# ──────────────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"
	cd frontend && npm install

# ──────────────────────────────────────────────────────────────────────────────
# Dev servers (run each in its own terminal — or use tmux / foreman)
# ──────────────────────────────────────────────────────────────────────────────
backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Start backend in one terminal:  make backend"
	@echo "Start frontend in another:      make frontend"

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-fast:
	pytest tests/ -x --tb=short -q

# ──────────────────────────────────────────────────────────────────────────────
# Lint
# ──────────────────────────────────────────────────────────────────────────────
lint: lint-py lint-js

lint-py:
	ruff check .
	ruff format --check .

lint-js:
	cd frontend && npm run lint

fix:
	ruff check . --fix
	ruff format .

# ──────────────────────────────────────────────────────────────────────────────
# Clean
# ──────────────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache"   -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/.next frontend/node_modules/.cache 2>/dev/null || true
	@echo "Clean done."
