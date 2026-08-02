"""Onboarding compose: default stack = all SPA PaddleX caps."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SERVICES = {
    "adapter",
    "bridge",
    "paddlex",
    "paddlex-objects",
    "paddlex-faces",
    "paddlex-ocr",
    "paddlex-pose",
    "paddlex-pedestrians",
    "paddlex-scene",
    "paddlex-face-id",
    "paddlex-scene-cls",
    "paddlex-instances",
    "paddlex-small-objects",
    "paddlex-anomaly",
    "paddlex-open-vocab",
}


def _docker_compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "compose", "version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


SKIP_REASON = "docker compose not available"


def _compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _host_ports(published: object) -> list[str]:
    """Collect host ports from compose config published ports entries."""
    out: list[str] = []
    if not isinstance(published, list):
        return out
    for entry in published:
        if isinstance(entry, dict):
            published_port = entry.get("published")
            if published_port is not None:
                out.append(str(published_port))
        elif isinstance(entry, str):
            # "8080:8080" or "127.0.0.1:8080:8080"
            left = entry.split("/")[0]
            parts = left.split(":")
            if len(parts) >= 2:
                out.append(parts[-2] if len(parts) == 3 else parts[0])
    return out


@unittest.skipUnless(_docker_compose_available(), SKIP_REASON)
class TestComposeOnboarding(unittest.TestCase):
    def test_default_services_include_all_spa_paddlex(self) -> None:
        proc = _compose("config", "--services")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        services = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
        missing = DEFAULT_SERVICES - services
        self.assertFalse(missing, f"missing {missing}; got {services}")
        # Profile-only services stay out of default.
        self.assertNotIn("bridge-demo", services)
        self.assertNotIn("paddlex-signs", services)

    def test_default_config_has_no_duplicate_host_ports(self) -> None:
        proc = _compose("config", "--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cfg = json.loads(proc.stdout)
        host_ports: list[str] = []
        for svc in (cfg.get("services") or {}).values():
            host_ports.extend(_host_ports(svc.get("ports")))
        duplicates = sorted({p for p in host_ports if host_ports.count(p) > 1})
        self.assertEqual(duplicates, [], f"duplicate host ports: {duplicates}")

    def test_default_bridge_volumes_exclude_docker_sock(self) -> None:
        proc = _compose("config", "--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cfg = json.loads(proc.stdout)
        bridge = (cfg.get("services") or {}).get("bridge") or {}
        volumes = bridge.get("volumes") or []
        serialized = json.dumps(volumes)
        self.assertNotIn(
            "docker.sock",
            serialized,
            "bridge must not mount docker.sock in default config",
        )


if __name__ == "__main__":
    unittest.main()
