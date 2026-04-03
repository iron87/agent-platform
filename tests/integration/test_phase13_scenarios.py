from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_quickstart_covers_bootstrap_sync_async_policy_hitl_and_cli() -> None:
    quickstart = _read("specs/001-ai-agent-platform/quickstart.md")

    expected_sections = [
        "Step 2 — Run the bootstrap script",
        "Step 2 — Run a one-shot synchronous invocation",
        "Step 4 — Submit and poll an async job",
        "Step 5 — Review or decide a pending approval",
        "tenant policy",
        "Tenant CLI Quickstart",
    ]

    for section in expected_sections:
        assert section in quickstart


def test_cli_examples_for_phase10_exist() -> None:
    for relpath in [
        "examples/us10_cli_end_to_end.sh",
        "examples/us10_cli_run_example.sh",
        "examples/us10_cli_jobs_example.sh",
        "examples/us10_cli_approvals_example.sh",
    ]:
        assert (ROOT / relpath).exists(), f"Missing example script: {relpath}"


def test_contract_mentions_core_runtime_paths() -> None:
    contract = _read("specs/001-ai-agent-platform/contracts/agent-api.yaml")

    for path in [
        "/run:",
        "/run/replay:",
        "/jobs:",
        "/jobs/{job_id}:",
        "/approvals/{approval_id}:",
        "/approvals/{approval_id}/decide:",
        "/agents:",
    ]:
        assert path in contract
