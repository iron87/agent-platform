#!/usr/bin/env python3
"""US8 example: policy hot-reload + version bump demonstration."""

from __future__ import annotations

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from agent.policy import get_policy_version, initialize_policies, start_hot_reload_loop


def _write_policy(path: Path, policy: dict) -> None:
    path.write_text(json.dumps(policy), encoding="utf-8")


def main() -> int:
    with TemporaryDirectory(prefix="2brain-us8-reload-") as tmp:
        root = Path(tmp)
        tenant_dir = root / "tenant-reload"
        tenant_dir.mkdir(parents=True, exist_ok=True)
        policy_file = tenant_dir / "policy.json"

        _write_policy(
            policy_file,
            {
                "version": 1,
                "blocked_categories": ["credentials"],
            },
        )

        initialize_policies(root)
        start_hot_reload_loop(root, interval_seconds=1)

        version_before = get_policy_version("tenant-reload")
        print("version_before:", version_before)

        _write_policy(
            policy_file,
            {
                "version": 2,
                "blocked_categories": ["credentials", "pii"],
            },
        )

        time.sleep(2)
        version_after = get_policy_version("tenant-reload")
        print("version_after:", version_after)

        if version_after is None or version_before is None:
            print("missing policy version")
            return 1
        if version_after <= version_before:
            print("hot-reload not detected")
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
