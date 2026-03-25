# 2brain Platform

A self-hosted AI agent platform. It allows teams to define agents, expose them via API, and manage synchronous or asynchronous executions with observability, policy controls, and containerized infrastructure components.

## What The Platform Does

- Exposes HTTP APIs to invoke agents.
- Supports synchronous and asynchronous modes.
- Includes a worker for long-running jobs.
- Centralizes Python configuration and dependencies.
- Provides standard commands for bootstrap, run, and quality checks.

## Current Implementation Status

Implemented tasks so far:

- T001: Python project metadata and dependency groups in pyproject.toml.
- T002: Developer targets in Makefile for bootstrap, run, and test.
- T003: Base package scaffolding for agent, api, and worker with __init__.py files.

## Requirements

- Python 3.12+
- Python virtual environment
- Make

## Quick Setup

1. Create or activate a virtual environment.
2. Install the project with dev dependencies:

```bash
python -m pip install -e '.[dev]'
```

## Main Commands

Using an explicit Python interpreter:

```bash
make PYTHON=/path/to/python test-all
make PYTHON=/path/to/python test-integration
make PYTHON=/path/to/python test-full
make PYTHON=/path/to/python run-api
make PYTHON=/path/to/python run-worker
make bootstrap
```

Target meaning:

- test-all: runs unit tests, lint, and type-check.
- test-integration: runs opt-in integration tests.
- test-full: runs test-all + test-integration.
- run-api: starts the local FastAPI service.
- run-worker: starts the RQ worker.
- bootstrap: runs infrastructure bootstrap.

## How To Test

### Fast Local Tests

```bash
make PYTHON=/path/to/python test-all

# Optional focused check for T003 package scaffolding
python -c "import agent, api, worker; print('ok')"
```

### Full Test Run

```bash
make PYTHON=/path/to/python test-full
```

Note: integration tests are opt-in and can be skipped when the stack is not running.

### Real Examples In This Repository

The repository includes setup tests in tests/test_project_setup.py and an integration health test in tests/integration/test_stack_health.py.

## Documentation Maintenance Rule

This README is a living document. After each implemented task in specs/001-ai-agent-platform/tasks.md, it must be updated with:

1. What was implemented.
2. How to use it.
3. How to verify it with tests or commands.

## Repository Structure

- agent/: agent runtime and orchestration.
- api/: FastAPI application.
- worker/: worker and async jobs.
- infra/: bootstrap and infrastructure configuration.
- tests/: unit and integration tests.
- specs/: specification, plan, and task documents.
