#!/usr/bin/env python3
"""US9 example: inspect and decide a pending approval request."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _request_json(url: str, *, method: str = "GET", api_key: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8")
            return status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8") or "{}"
        raise RuntimeError(f"HTTP {exc.code} {payload}") from exc


def main() -> int:
    base_url = _env("AGENT_API_BASE_URL", "http://localhost:8000/api/v1")
    api_key = _env("AGENT_API_KEY")
    approval_id = _env("AGENT_APPROVAL_ID")
    reviewer_id = _env("AGENT_REVIEWER_ID", "ops@example.com")
    decision = _env("AGENT_APPROVAL_DECISION", "approve").lower()
    reason = os.getenv("AGENT_APPROVAL_REASON", "Approved via US9 example")

    get_url = f"{base_url.rstrip('/')}/approvals/{approval_id}"
    status, approval = _request_json(get_url, api_key=api_key)
    print(json.dumps({"approval_get_status": status, "approval": approval}, indent=2))

    if approval.get("status") != "pending":
        print("Approval is not pending; skipping decision step.")
        return 0

    approved = decision in {"approve", "approved", "true", "1", "yes"}
    post_url = f"{base_url.rstrip('/')}/approvals/{approval_id}/decide"
    decision_payload = {
        "approved": approved,
        "reviewer_id": reviewer_id,
        "reason": reason,
    }
    status, decided = _request_json(
        post_url,
        method="POST",
        api_key=api_key,
        payload=decision_payload,
    )
    print(json.dumps({"approval_decide_status": status, "decision": decided}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
