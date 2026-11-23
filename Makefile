.PHONY: help install install-dev test clean

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

help:
	@echo "Available targets:"
	@echo "  install      Create venv and install package"
	@echo "  install-dev  Create venv and install package with dev dependencies"
	@echo "  test         Run pytest test suite"
	@echo "  clean        Remove build artifacts and caches"

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/python
	$(PIP) install -e .

install-dev: $(VENV)/bin/python
	$(PIP) install -e ".[dev]"

test:
	$(PYTEST) -v

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
