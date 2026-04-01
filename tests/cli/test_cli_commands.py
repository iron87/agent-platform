from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = ROOT / "packages" / "tenant-cli"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cli_workspace_and_package_manifest_exist() -> None:
    root_package = json.loads(_read(ROOT / "package.json"))
    cli_package = json.loads(_read(CLI_ROOT / "package.json"))

    assert "packages/*" in root_package["workspaces"]
    assert cli_package["name"] == "@2brain/tenant-cli"
    assert cli_package["bin"]["2brain"]
    deps = cli_package["dependencies"]
    assert "ink" in deps
    assert "react" in deps


def test_cli_sources_cover_config_run_and_jobs_flows() -> None:
    cli_entry = _read(CLI_ROOT / "src" / "cli.tsx")
    config_cmd = _read(CLI_ROOT / "src" / "commands" / "config.tsx")
    run_cmd = _read(CLI_ROOT / "src" / "commands" / "run.tsx")
    chat_cmd = _read(CLI_ROOT / "src" / "commands" / "chat.tsx")
    jobs_cmd = _read(CLI_ROOT / "src" / "commands" / "jobs.tsx")
    client = _read(CLI_ROOT / "src" / "api" / "client.ts")

    assert "config" in cli_entry
    assert "run" in cli_entry
    assert "jobs" in cli_entry
    assert "approvals" in cli_entry

    assert "config set" in config_cmd or "setCommand" in config_cmd
    assert "--profile" in run_cmd
    assert "--json" in run_cmd
    assert "session_id" in chat_cmd
    assert "submit" in jobs_cmd and "status" in jobs_cmd and "wait" in jobs_cmd
    assert "X-API-Key" in client
    assert "/run" in client
    assert "/jobs" in client
