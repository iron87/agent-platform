from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pyproject_has_required_metadata_and_dependency_groups() -> None:
    data = tomllib.loads(_read("pyproject.toml"))

    project = data["project"]
    assert project["name"] == "2brain-platform"
    assert project["requires-python"] == ">=3.12"

    deps = set(project["dependencies"])
    assert any(dep.startswith("fastapi") for dep in deps)
    assert any(dep.startswith("pydantic") for dep in deps)
    assert any(dep.startswith("langgraph") for dep in deps)

    optional = project["optional-dependencies"]
    dev = set(optional["dev"])
    assert any(dep.startswith("pytest") for dep in dev)
    assert any(dep.startswith("ruff") for dep in dev)
    assert any(dep.startswith("mypy") for dep in dev)


def test_pyproject_package_discovery_is_scoped() -> None:
    data = tomllib.loads(_read("pyproject.toml"))
    find_cfg = data["tool"]["setuptools"]["packages"]["find"]

    assert find_cfg["where"] == ["."]
    assert "agent*" in find_cfg["include"]
    assert "api*" in find_cfg["include"]
    assert "worker*" in find_cfg["include"]


def test_makefile_has_bootstrap_test_and_run_targets() -> None:
    makefile = _read("Makefile")

    required_targets = [
        "bootstrap:",
        "run:",
        "run-api:",
        "run-worker:",
        "test:",
        "test-unit:",
        "test-integration:",
        "lint:",
        "format:",
    ]

    for target in required_targets:
        assert target in makefile


def test_ignore_files_have_critical_patterns() -> None:
    gitignore = _read(".gitignore")
    dockerignore = _read(".dockerignore")

    for expected in ["__pycache__/", "*.pyc", ".venv/", ".env", ".DS_Store"]:
        assert expected in gitignore

    for expected in [".git/", "__pycache__/", "*.pyc", ".env", "*.log*"]:
        assert expected in dockerignore
