.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
REELS_SYNC := $(VENV)/bin/reels-sync

CONFIG ?=
VAULT ?=
LIMIT ?= 10
URL ?=
SHORTCODE ?=
EXPORT_DIR ?=
K ?=
HOST ?= 127.0.0.1
PORT ?= 8765

GLOBAL_FLAGS := $(if $(CONFIG),--config "$(CONFIG)",) $(if $(VAULT),--vault "$(VAULT)",)

.PHONY: help venv install install-dev install-local install-all update-yt-dlp init-config init doctor \
        test test-fast test-match test-cov lint typecheck check-docs check-release check-site verify \
        stats stats-json ingest import-ig process-dry process retry-failed reprocess reprocess-all telegram mcp serve \
        docker-build docker-process docker-telegram build build-extension build-obsidian-plugin build-safari-extension clean clean-all

help: ## Show available targets grouped by category
	@echo "reels-wiki Makefile targets"
	@echo ""
	@echo "Variables: CONFIG= VAULT= LIMIT=$(LIMIT) URL= SHORTCODE= EXPORT_DIR= K= HOST=$(HOST) PORT=$(PORT)"
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

test-cov: ## Run pytest with coverage report and 70% minimum threshold
	$(PYTEST) -v --cov=reels_wiki --cov-report=term-missing --cov-fail-under=70

lint: ## Run ruff linter on src and tests
	$(RUFF) check src tests

typecheck: ## Run mypy type checker on src/reels_wiki
	$(MYPY) src/reels_wiki

check-docs: ## Verify README links exist and polished docs have no em-dashes
	@$(PYTHON) -c 'import pathlib, re; \
		docs = [pathlib.Path("README.md")] + sorted(pathlib.Path("docs").glob("*.md")); \
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
		ext_ver = json.loads(pathlib.Path("extension/manifest.json").read_text())["version"]; \
		obs_ver = json.loads(pathlib.Path("obsidian-plugin/manifest.json").read_text())["version"]; \
		assert m_ver == py_ver == init_ver == ext_ver == obs_ver, f"Version mismatch: manifest={m_ver}, pyproject={py_ver}, __init__={init_ver}, extension={ext_ver}, obsidian={obs_ver}"; \
		assert "packages" in cfg and "." in cfg["packages"]; \
		print(f"Release config and version parity OK ({m_ver}).")'
	@$(VENV_PYTHON) -c 'import yaml, pathlib; yaml.safe_load(pathlib.Path(".github/workflows/release-please.yml").read_text()); print("Workflow YAML syntax OK.")' 2>/dev/null || \
		$(PYTHON) -c 'import yaml, pathlib; yaml.safe_load(pathlib.Path(".github/workflows/release-please.yml").read_text()); print("Workflow YAML syntax OK.")'

check-site: ## Validate site/, extension/, and obsidian-plugin/ JS, JSON, and XML files
	@if command -v node >/dev/null 2>&1; then \
		node --check site/index.js && node --check extension/background.js && node --check extension/popup.js && node --check obsidian-plugin/main.js; \
	fi
	@$(PYTHON) -c 'import json, pathlib, xml.etree.ElementTree as ET; \
		json.loads(pathlib.Path("extension/manifest.json").read_text()); \
		json.loads(pathlib.Path("obsidian-plugin/manifest.json").read_text()); \
		ET.fromstring(pathlib.Path("site/sitemap.xml").read_text()); \
		print("Site and extension checks passed.")'

verify: check-docs check-release check-site lint typecheck test-cov ## Run all docs, release, site, lint, type, and test gates

# --- CLI Workflows
init: ## Run interactive setup wizard (config.yaml + .env + doctor)
	$(REELS_SYNC) $(GLOBAL_FLAGS) init

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

serve: ## Start local HTTP ingest server (HOST=$(HOST) PORT=$(PORT))
	$(REELS_SYNC) $(GLOBAL_FLAGS) serve --host $(HOST) --port $(PORT)

# --- Docker
docker-build: ## Build Docker image via docker compose
	docker compose build

docker-process: ## Run queued processor inside Docker container
	docker compose run --rm reels-process

docker-telegram: ## Start Telegram capture bot container in background
	docker compose up -d reels-telegram

# --- Build & Cleanup
build: $(VENV_PYTHON) ## Build sdist and wheel distributions into dist/
	$(VENV_PYTHON) -m pip install --upgrade build
	$(VENV_PYTHON) -m build

build-extension: ## Package Chrome/Firefox extension ZIP into dist/
	@mkdir -p dist
	@cd extension && rm -f ../dist/reels-wiki-extension.zip && zip -q -r -X ../dist/reels-wiki-extension.zip manifest.json background.js popup.html popup.css popup.js icons/ -x "*.DS_Store"
	@echo "Built dist/reels-wiki-extension.zip"

build-obsidian-plugin: ## Package native Obsidian plugin ZIP into dist/
	@mkdir -p dist
	@cd obsidian-plugin && rm -f ../dist/reels-wiki-obsidian-plugin.zip && zip -q -r -X ../dist/reels-wiki-obsidian-plugin.zip manifest.json main.js styles.css README.md -x "*.DS_Store"
	@echo "Built dist/reels-wiki-obsidian-plugin.zip"

build-safari-extension: ## Generate Safari Web Extension Xcode project into dist/safari-extension
	@mkdir -p dist
	@xcrun safari-web-extension-converter extension/ \
		--project-location dist/safari-extension \
		--app-name "reels-wiki Capture" \
		--bundle-identifier com.atacanymc.reels-wiki \
		--macos-only --force --no-open --no-prompt
	@echo "Generated dist/safari-extension"

clean: ## Remove build artifacts and Python caches
	rm -rf build/ dist/ *.egg-info .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-all: clean ## Remove build artifacts, caches, and $(VENV)
	rm -rf $(VENV)
