#!/usr/bin/env python3
"""US2 example: authenticated synchronous invocation against /api/v1/run."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request


def main() -> int:
    base_url = os.getenv("AGENT_BASE_URL", "http://localhost:8000").rstrip("/")
    api_key = os.getenv("AGENT_API_KEY", "")
    agent_id = os.getenv("AGENT_ID", "00000000-0000-0000-0000-000000000001")
    timeout_seconds = int(os.getenv("AGENT_TIMEOUT_SECONDS", "180"))

    if not api_key:
        print("Set AGENT_API_KEY before running this script.", file=sys.stderr)
        return 1

    payload = {
        "agent_id": agent_id,
        "input": (
            "Customer ticket: user cannot reset password and receives code 429. "
            "Provide a triage summary with priority and next action."
        ),
        "metadata": {
            "source": "support-system",
            "ticket_id": "SUP-1042",
            "tenant": "acme",
        },
    }

    request = urllib.request.Request(
        url=f"{base_url}/api/v1/run",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
        return 2
    except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
        print(
            "Request timed out while waiting for /api/v1/run. "
            f"Increase AGENT_TIMEOUT_SECONDS (current: {timeout_seconds}).",
            file=sys.stderr,
        )
        print(f"Error details: {exc}", file=sys.stderr)
        return 3

    print("status:", response.status)
    print("job_id:", body.get("job_id"))
    print("trace_id:", body.get("trace_id"))
    print("output:\n", body.get("output", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
