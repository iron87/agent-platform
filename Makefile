.PHONY: bootstrap run run-api run-worker test test-all test-full test-unit test-integration lint typecheck format

PYTHON ?= python

bootstrap:
	bash infra/bootstrap.sh

run: run-api

run-api:
	$(PYTHON) -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	$(PYTHON) -m rq worker agent_jobs

test: test-unit

test-all: test-unit lint typecheck

test-full: test-all test-integration

test-unit:
	$(PYTHON) -m pytest tests/ -v

test-integration:
	TEST_INTEGRATION=true $(PYTHON) -m pytest tests/integration/ -v

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy .

format:
	$(PYTHON) -m ruff format .
