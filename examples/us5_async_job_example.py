#!/usr/bin/env python3
"""US5 example: submit an async job and poll until completion."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

TERMINAL_STATES = {"completed", "failed", "interrupted"}


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
    poll_interval_seconds = float(os.getenv("AGENT_POLL_INTERVAL_SECONDS", "2"))
    timeout_seconds = int(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))

    if not api_key:
        print("Set AGENT_API_KEY before running this script.", file=sys.stderr)
        return 1

    payload = {
        "agent_id": agent_id,
        "input": os.getenv(
            "AGENT_ASYNC_INPUT",
            "Analyze the customer backlog and return a short triage summary with next actions.",
        ),
        "metadata": {
            "source": "examples/us5_async_job_example.py",
            "tenant": "acme",
        },
    }

    try:
        submit_status, submit_body = _json_request(
            url=f"{base_url}/api/v1/jobs",
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            method="POST",
            payload=payload,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        return 2
    except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
        print(
            f"Job submission failed: {exc}. "
            f"Make sure the local stack is running and reachable at {base_url} "
            "(start Docker Desktop and rerun `bash infra/bootstrap-light.sh` if needed).",
            file=sys.stderr,
        )
        return 3

    job_id = str(submit_body.get("job_id") or "")
    print("submit_status:", submit_status)
    print("job_id:", job_id)

    if not job_id:
        print("Missing job_id in submit response.", file=sys.stderr)
        return 4

    deadline = time.time() + timeout_seconds
    last_status = None

    while time.time() < deadline:
        try:
            _, job_body = _json_request(
                url=f"{base_url}/api/v1/jobs/{job_id}",
                api_key=api_key,
                timeout_seconds=timeout_seconds,
            )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            print(f"Polling failed with HTTP {exc.code}: {detail}", file=sys.stderr)
            return 5
        except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            print(
                f"Polling failed: {exc}. "
                f"Check that `agent-api` and `agent-worker` are reachable at {base_url}.",
                file=sys.stderr,
            )
            return 6

        current_status = str(job_body.get("status"))
        if current_status != last_status:
            print("status:", current_status)
            last_status = current_status

        if current_status in TERMINAL_STATES:
            print("trace_id:", job_body.get("trace_id"))
            if current_status == "completed":
                print("output:\n", job_body.get("output", ""))
                return 0
            if current_status == "interrupted":
                print("pending_approval_id:", job_body.get("pending_approval_id"))
                return 7
            print("error:", job_body.get("error"), file=sys.stderr)
            return 8

        time.sleep(poll_interval_seconds)

    print(
        f"Timed out waiting for job completion after {timeout_seconds}s. "
        "Check agent-worker logs if the job stays pending.",
        file=sys.stderr,
    )
    return 9


if __name__ == "__main__":
    raise SystemExit(main())
