#!/usr/bin/env python3
"""US3 example: 3-turn session conversation against /api/v1/run."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request


def _post_run(base_url: str, api_key: str, payload: dict, timeout: int) -> tuple[int, dict]:
    req = urllib.request.Request(
        url=f"{base_url}/api/v1/run",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
        return response.status, body


def main() -> int:
    base_url = os.getenv("AGENT_BASE_URL", "http://localhost:8000").rstrip("/")
    api_key = os.getenv("AGENT_API_KEY", "")
    agent_id = os.getenv("AGENT_ID", "00000000-0000-0000-0000-000000000001")
    session_id = os.getenv("AGENT_SESSION_ID", "us3-demo-session-1")
    timeout_seconds = int(os.getenv("AGENT_TIMEOUT_SECONDS", "240"))

    if not api_key:
        print("Set AGENT_API_KEY before running this script.", file=sys.stderr)
        return 1

    turns = [
        "Mi chiamo Federico.",
        "Sto preparando una demo US3.",
        "Come mi chiamo e cosa sto preparando?",
    ]

    try:
        for idx, text in enumerate(turns, start=1):
            payload = {
                "agent_id": agent_id,
                "session_id": session_id,
                "input": text,
                "metadata": {"source": "us3-session-example", "turn": idx},
            }
            status, body = _post_run(base_url, api_key, payload, timeout_seconds)
            print(f"turn={idx} status={status} session_id={body.get('session_id')}")
            print("output:", (body.get("output") or "").replace("\n", " "))
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
