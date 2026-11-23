.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
REELS_SYNC := $(VENV)/bin/reels-sync

CONFIG ?=
VAULT ?=
LIMIT ?= 10
URL ?=
SHORTCODE ?=
EXPORT_DIR ?=
K ?=

GLOBAL_FLAGS := $(if $(CONFIG),--config "$(CONFIG)",) $(if $(VAULT),--vault "$(VAULT)",)

.PHONY: help venv install install-dev install-local install-all update-yt-dlp init-config doctor \
        test test-fast test-match check-docs check-release verify \
        stats stats-json ingest import-ig process-dry process retry-failed reprocess reprocess-all telegram mcp \
        build clean clean-all

help: ## Show available targets grouped by category
	@echo "reels-wiki Makefile targets"
	@echo ""
	@echo "Variables: CONFIG= VAULT= LIMIT=$(LIMIT) URL= SHORTCODE= EXPORT_DIR= K="
	@echo ""
	@awk 'BEGIN {FS = ":.*## "} \
		/^# --- / { printf "\n\033[1m%s\033[0m\n", substr($$0, 7); next } \
		/^[a-zA-Z0-9_.-]+:.*## / { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- Setup & Environment
$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)

venv: $(VENV_PYTHON) ## Create Python virtual environment in $(VENV)

install: $(VENV_PYTHON) ## Install package in editable mode
	$(PIP) install -e .

install-dev: $(VENV_PYTHON) ## Install package with dev dependencies
	$(PIP) install -e ".[dev]"

install-local: $(VENV_PYTHON) ## Install package with local faster-whisper dependencies
	$(PIP) install -e ".[local]"

install-all: $(VENV_PYTHON) ## Install package with dev and local dependencies
	$(PIP) install -e ".[dev,local]"

update-yt-dlp: $(VENV_PYTHON) ## Upgrade yt-dlp to latest release
	$(PIP) install -U yt-dlp

init-config: ## Copy config.example.yaml to config.yaml if missing
	@if [ -f config.yaml ]; then \
		echo "config.yaml already exists, skipping."; \
	else \
		cp config.example.yaml config.yaml && echo "Created config.yaml from config.example.yaml."; \
	fi

doctor: ## Check Python, ffmpeg, virtual environment, and config files
	@echo "Python: $$($(PYTHON) --version 2>&1)"
	@echo "Venv:   $$([ -x $(VENV_PYTHON) ] && $(VENV_PYTHON) --version || echo 'not created')"
	@echo "ffmpeg: $$(command -v ffmpeg >/dev/null 2>&1 && ffmpeg -version | head -n 1 || echo 'missing (required only for audio/vision fallbacks)')"
	@echo "config: $$([ -f config.yaml ] && echo 'config.yaml present' || echo 'config.yaml missing')"
	@echo ".env:   $$([ -f .env ] && echo '.env present' || echo '.env missing')"

# --- Testing & Quality
test: ## Run full pytest suite with verbose output
	$(PYTEST) -v

test-fast: ## Run pytest stopping on first failure without verbose tracebacks
	$(PYTEST) -x -q --tb=short

test-match: ## Run pytest matching K=<pattern>
	@test -n "$(K)" || (echo "Usage: make test-match K=<pattern>" && exit 1)
	$(PYTEST) -v -k "$(K)"

check-docs: ## Verify README links exist and polished docs have no em-dashes
	@$(PYTHON) -c 'import pathlib, re; \
		docs = [pathlib.Path(p) for p in ["README.md", "docs/step-by-step.md", "docs/example-walkthrough.md"]]; \
		[(_ for _ in ()).throw(AssertionError(f"Em-dash found in {p}")) for p in docs if "—" in p.read_text()]; \
		readme = pathlib.Path("README.md").read_text(); \
		links = re.findall(r"\]\(([^)#http][^)]*)\)", readme) + re.findall(r"src=\"([^\"]+)\"", readme); \
		missing = [l for l in links if not pathlib.Path(l).exists()]; \
		assert not missing, f"Missing links: {missing}"; \
		print(f"Docs check passed ({len(docs)} markdown files, {len(links)} README links).")'

check-release: ## Validate release-please JSON/YAML and version parity
	@$(PYTHON) -c 'import json, pathlib, re; \
		cfg = json.loads(pathlib.Path("release-please-config.json").read_text()); \
		manifest = json.loads(pathlib.Path(".release-please-manifest.json").read_text()); \
		m_ver = manifest["."]; \
		py_ver = re.search(r"^version\s*=\s*\"([^\"]+)\"", pathlib.Path("pyproject.toml").read_text(), re.M).group(1); \
		init_ver = re.search(r"__version__\s*=\s*\"([^\"]+)\"", pathlib.Path("src/reels_wiki/__init__.py").read_text()).group(1); \
		assert m_ver == py_ver == init_ver, f"Version mismatch: manifest={m_ver}, pyproject={py_ver}, __init__={init_ver}"; \
		assert "packages" in cfg and "." in cfg["packages"]; \
		print(f"Release config and version parity OK ({m_ver}).")'
	@$(VENV_PYTHON) -c 'import yaml, pathlib; yaml.safe_load(pathlib.Path(".github/workflows/release-please.yml").read_text()); print("Workflow YAML syntax OK.")' 2>/dev/null || \
		$(PYTHON) -c 'import yaml, pathlib; yaml.safe_load(pathlib.Path(".github/workflows/release-please.yml").read_text()); print("Workflow YAML syntax OK.")'

verify: check-docs check-release test ## Run doc checks, release parity checks, and pytest suite

# --- CLI Workflows
stats: ## Show queue statistics
	$(REELS_SYNC) $(GLOBAL_FLAGS) stats

stats-json: ## Show queue statistics in JSON format
	$(REELS_SYNC) $(GLOBAL_FLAGS) --json stats

ingest: ## Enqueue a single Reel URL (make ingest URL=<instagram_url>)
	@test -n "$(URL)" || (echo "Usage: make ingest URL=<instagram_url>" && exit 1)
	$(REELS_SYNC) $(GLOBAL_FLAGS) ingest "$(URL)"

import-ig: ## Import Instagram data export (make import-ig EXPORT_DIR=<path>)
	@test -n "$(EXPORT_DIR)" || (echo "Usage: make import-ig EXPORT_DIR=<path>" && exit 1)
	$(REELS_SYNC) $(GLOBAL_FLAGS) import-ig "$(EXPORT_DIR)"

process-dry: ## Preview pending queue items without running extraction or LLM calls
	$(REELS_SYNC) $(GLOBAL_FLAGS) process --dry-run

process: ## Process pending queue items (LIMIT=$(LIMIT))
	$(REELS_SYNC) $(GLOBAL_FLAGS) process --limit $(LIMIT)

retry-failed: ## Retry failed queue items (LIMIT=$(LIMIT))
	$(REELS_SYNC) $(GLOBAL_FLAGS) process --retry-failed --limit $(LIMIT)

reprocess: ## Re-synthesize note from stored artifact (make reprocess SHORTCODE=<code>)
	@test -n "$(SHORTCODE)" || (echo "Usage: make reprocess SHORTCODE=<code>" && exit 1)
	$(REELS_SYNC) $(GLOBAL_FLAGS) reprocess "$(SHORTCODE)"

reprocess-all: ## Re-synthesize all stored artifacts
	$(REELS_SYNC) $(GLOBAL_FLAGS) reprocess --all

telegram: ## Start the Telegram capture bot
	$(REELS_SYNC) $(GLOBAL_FLAGS) telegram

mcp: ## Start the MCP server on stdio
	$(REELS_SYNC) $(GLOBAL_FLAGS) mcp

# --- Build & Cleanup
build: $(VENV_PYTHON) ## Build sdist and wheel distributions into dist/
	$(VENV_PYTHON) -m pip install --upgrade build
	$(VENV_PYTHON) -m build

clean: ## Remove build artifacts and Python caches
	rm -rf build/ dist/ *.egg-info .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-all: clean ## Remove build artifacts, caches, and $(VENV)
	rm -rf $(VENV)
