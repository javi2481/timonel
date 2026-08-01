"""Onboarding compose: CORE default vs profile full."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    def test_default_services_are_core_only(self) -> None:
        proc = _compose("config", "--services")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        services = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
        self.assertEqual(
            services,
            {"adapter", "bridge", "paddlex-objects", "paddlex-faces"},
        )

    def test_full_profile_includes_hot_paddlex(self) -> None:
        env_full = ROOT / ".env.full.example"
        self.assertTrue(env_full.is_file(), ".env.full.example missing")
        proc = _compose(
            "--profile",
            "full",
            "--env-file",
            str(env_full),
            "config",
            "--services",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        services = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
        required = {
            "paddlex",
            "paddlex-ocr",
            "paddlex-pose",
            "paddlex-objects",
            "paddlex-faces",
            "adapter",
            "bridge",
        }
        missing = required - services
        self.assertFalse(missing, f"missing {missing}; got {services}")

    def test_full_config_has_no_duplicate_host_ports(self) -> None:
        env_full = ROOT / ".env.full.example"
        proc = _compose(
            "--profile",
            "full",
            "--env-file",
            str(env_full),
            "config",
            "--format",
            "json",
        )
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
            "bridge must not mount docker.sock in default CORE config",
        )


if __name__ == "__main__":
    unittest.main()
