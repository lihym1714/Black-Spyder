PYTHON ?= python3
VENV_PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,$(PYTHON))

.PHONY: bootstrap dry-run format-help tree

bootstrap:
	$(VENV_PYTHON) tools/bootstrap.py

dry-run:
	$(VENV_PYTHON) tools/dry_run.py

format-help:
	@printf '%s\n' 'Recommended formatters (optional):'
	@printf '%s\n' '  python -m pip install black ruff'
	@printf '%s\n' '  python -m black mcp tools'
	@printf '%s\n' '  python -m ruff check mcp tools'

tree:
	@if command -v tree >/dev/null 2>&1; then tree .; else $(VENV_PYTHON) tools/print_tree.py; fi
