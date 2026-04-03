#!/usr/bin/env python3
"""US8 example: redaction-only policy behavior."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from agent.policy import apply_policy, get_rails, initialize_policies


async def _run() -> int:
    with TemporaryDirectory(prefix="2brain-us8-redact-") as tmp:
        root = Path(tmp)
        tenant_dir = root / "tenant-redaction"
        tenant_dir.mkdir(parents=True, exist_ok=True)

        policy = {
            "version": 1,
            "redaction_rules": [
                {
                    "name": "email",
                    "pattern": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                    "replacement": "[EMAIL]",
                },
                {
                    "name": "phone",
                    "pattern": r"\b\+?[0-9][0-9\- ]{7,}[0-9]\b",
                    "replacement": "[PHONE]",
                },
            ],
        }
        (tenant_dir / "policy.json").write_text(json.dumps(policy), encoding="utf-8")

        initialize_policies(root)
        bundle = get_rails("tenant-redaction")
        if bundle is None:
            print("policy handle not found")
            return 1

        text = "Contact alice@example.com or +39 333 123 4567 for updates."
        redacted, meta = await apply_policy(
            bundle,
            text,
            tenant_id="tenant-redaction",
            stage="output",
        )

        print("original:", text)
        print("redacted:", redacted)
        print("meta:", json.dumps(meta, indent=2))

    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
