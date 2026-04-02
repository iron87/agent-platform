#!/usr/bin/env python3
"""US7 example: trace review and replay via /api/v1/run and /api/v1/run/replay."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request


def _json_request(
    *,
    url: str,
    api_key: str,
    timeout_seconds: int,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url=url,
        method=method,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    base_url = os.getenv("AGENT_BASE_URL", "http://localhost:8000").rstrip("/")
    api_key = os.getenv("AGENT_API_KEY", "")
    agent_id = os.getenv("AGENT_ID", "00000000-0000-0000-0000-000000000001")
    timeout_seconds = int(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))

    run_input = os.getenv(
        "AGENT_US7_INPUT",
        "Investigate why customer notifications were delayed and provide a short root-cause summary.",
    )
    replay_input = os.getenv("AGENT_US7_REPLAY_INPUT", run_input)

    if not api_key:
        print("Set AGENT_API_KEY before running this script.", file=sys.stderr)
        return 1

    run_payload = {
        "agent_id": agent_id,
        "input": run_input,
        "metadata": {
            "source": "examples/us7_trace_replay_example.py",
            "flow": "initial_run",
        },
    }

    try:
        run_status, run_body = _json_request(
            url=f"{base_url}/api/v1/run",
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            method="POST",
            payload=run_payload,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"HTTP {exc.code} during initial run: {detail}", file=sys.stderr)
        return 2
    except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
        print(
            f"Initial run failed: {exc}. Make sure stack is running at {base_url}.",
            file=sys.stderr,
        )
        return 3

    trace_id = str(run_body.get("trace_id") or "")
    print("initial_status:", run_status)
    print("initial_job_id:", run_body.get("job_id"))
    print("initial_trace_id:", trace_id)

    if not trace_id:
        print(
            "Missing trace_id from initial run; replay cannot continue.",
            file=sys.stderr,
        )
        return 4

    replay_payload = {
        "trace_id": trace_id,
        "agent_id": agent_id,
        "input": replay_input,
        "metadata": {
            "source": "examples/us7_trace_replay_example.py",
            "flow": "replay",
        },
    }

    try:
        replay_status, replay_body = _json_request(
            url=f"{base_url}/api/v1/run/replay",
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            method="POST",
            payload=replay_payload,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"HTTP {exc.code} during replay: {detail}", file=sys.stderr)
        return 5
    except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
        print(
            f"Replay request failed: {exc}. Verify /api/v1/run/replay is reachable.",
            file=sys.stderr,
        )
        return 6

    print("replay_status:", replay_status)
    print("replay_job_id:", replay_body.get("job_id"))
    print("replay_trace_id:", replay_body.get("trace_id"))
    print("replay_output:\n", replay_body.get("output", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
