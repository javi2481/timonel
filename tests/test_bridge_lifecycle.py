"""Unit tests for bridge container lifecycle (pause/unpause idle + wake)."""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, patch

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bridge.lifecycle import (  # noqa: E402
    ContainerLifecycle,
    LifecycleConfig,
)


class FakeDocker:
    def __init__(self, states: Optional[dict[str, str]] = None) -> None:
        self.states = dict(states or {})
        self.paused: list[str] = []
        self.unpaused: list[str] = []

    async def container_state(self, name: str) -> Optional[str]:
        return self.states.get(name)

    async def pause(self, name: str) -> bool:
        self.paused.append(name)
        self.states[name] = "paused"
        return True

    async def unpause(self, name: str) -> bool:
        self.unpaused.append(name)
        self.states[name] = "running"
        return True

    async def aclose(self) -> None:
        return None


def _cfg(**kwargs) -> LifecycleConfig:
    base = dict(
        enabled=True,
        idle_pause_s=60.0,
        docker_sock="/var/run/docker.sock",
        cap_containers={
            "pedestrians": "tm-paddlex-pedestrians",
            "face_id": "tm-paddlex-face-id",
        },
    )
    base.update(kwargs)
    return LifecycleConfig(**base)


class TestLifecycleConfig(unittest.TestCase):
    def test_from_env_defaults_off(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLE_CONTAINER_LIFECYCLE", None)
            os.environ.pop("LIFECYCLE_PAUSE_CAPS", None)
            cfg = LifecycleConfig.from_env()
        self.assertFalse(cfg.enabled)
        self.assertIn("pedestrians", cfg.cap_containers)
        self.assertNotIn("open_vocab", cfg.cap_containers)

    def test_custom_pause_caps(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ENABLE_CONTAINER_LIFECYCLE": "true",
                "LIFECYCLE_PAUSE_CAPS": "pedestrians,face_id=tm-custom-fid",
                "CONTAINER_IDLE_PAUSE_S": "30",
            },
            clear=False,
        ):
            cfg = LifecycleConfig.from_env()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.idle_pause_s, 30.0)
        self.assertEqual(cfg.cap_containers["pedestrians"], "tm-paddlex-pedestrians")
        self.assertEqual(cfg.cap_containers["face_id"], "tm-custom-fid")


class TestContainerLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_awake_unpauses(self) -> None:
        engine = FakeDocker(
            {
                "tm-paddlex-pedestrians": "paused",
                "tm-paddlex-face-id": "running",
            }
        )
        life = ContainerLifecycle(config=_cfg(), engine=engine)
        woken = await life.ensure_awake({"pedestrians", "face_id", "open_vocab"})
        self.assertEqual(woken, ["pedestrians"])
        self.assertEqual(engine.unpaused, ["tm-paddlex-pedestrians"])
        self.assertEqual(engine.states["tm-paddlex-pedestrians"], "running")

    async def test_pause_idle_respects_touch(self) -> None:
        engine = FakeDocker(
            {
                "tm-paddlex-pedestrians": "running",
                "tm-paddlex-face-id": "running",
            }
        )
        life = ContainerLifecycle(config=_cfg(idle_pause_s=10.0), engine=engine)
        life.touch(["pedestrians"])
        # face_id never touched → idle → pause
        paused = await life.pause_idle(now=time.monotonic())
        self.assertEqual(paused, ["face_id"])
        self.assertEqual(engine.paused, ["tm-paddlex-face-id"])

        # pedestrians recently touched → not paused
        self.assertEqual(engine.states["tm-paddlex-pedestrians"], "running")

        # Advance past idle for pedestrians
        past = time.monotonic() + 100.0
        paused2 = await life.pause_idle(now=past)
        self.assertEqual(paused2, ["pedestrians"])

    async def test_disabled_noop(self) -> None:
        engine = FakeDocker({"tm-paddlex-pedestrians": "running"})
        life = ContainerLifecycle(config=_cfg(enabled=False), engine=engine)
        self.assertEqual(await life.ensure_awake(["pedestrians"]), [])
        self.assertEqual(await life.pause_idle(), [])
        self.assertEqual(engine.paused, [])
        self.assertEqual(engine.unpaused, [])

    async def test_pause_all_on_start(self) -> None:
        engine = FakeDocker(
            {
                "tm-paddlex-pedestrians": "running",
                "tm-paddlex-face-id": "running",
            }
        )
        life = ContainerLifecycle(config=_cfg(idle_pause_s=999.0), engine=engine)
        paused = await life.pause_all_pausable()
        self.assertEqual(sorted(paused), ["face_id", "pedestrians"])


class TestRunDetectionsLifecycleHook(unittest.IsolatedAsyncioTestCase):
    async def test_wave2_calls_ensure_awake(self) -> None:
        import numpy as np

        from bridge import main as bridge_main

        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        calls: list[set[str]] = []

        class TrackingLife:
            enabled = True

            async def ensure_awake(self, names):
                s = set(names)
                calls.append(s)
                return sorted(s & {"pedestrians", "face_id"})

        async def fake_fetch(_client):
            return {"vehicles", "objects", "faces", "pedestrians", "face_id"}

        async def fake_gather(client, caps, jpeg, frame_wh, open_vocab_prompt=None):
            out = {}
            for c in caps:
                if c.name == "vehicles":
                    out[c.name] = [
                        {
                            "label": "car",
                            "score": 0.9,
                            "bbox": [0, 0, 10, 10],
                            "entity_type": "vehicle",
                        }
                    ]
                elif c.name == "objects":
                    out[c.name] = [
                        {
                            "label": "person",
                            "score": 0.9,
                            "bbox": [1, 1, 8, 8],
                            "entity_type": "object",
                        }
                    ]
                elif c.name == "faces":
                    out[c.name] = [
                        {
                            "label": "face",
                            "score": 0.8,
                            "bbox": [2, 2, 5, 5],
                            "entity_type": "face",
                        }
                    ]
                else:
                    out[c.name] = []
            return out

        with patch.dict(os.environ, {"ENABLE_EVIDENCE_CASCADE": "true"}):
            with patch.object(
                bridge_main, "fetch_active_capability_names", fake_fetch
            ):
                with patch.object(bridge_main, "gather_capabilities", fake_gather):
                    with patch.object(
                        bridge_main,
                        "enrich_vehicles_with_plates",
                        new=AsyncMock(),
                    ):
                        with patch.object(
                            bridge_main,
                            "draw_preview",
                            return_value=b"jpeg",
                        ):
                            with patch.object(
                                bridge_main,
                                "encode_jpeg",
                                return_value=b"raw",
                            ):
                                dets, degraded, _ = await bridge_main.run_detections(
                                    AsyncMock(),
                                    frame,
                                    lifecycle=TrackingLife(),  # type: ignore[arg-type]
                                )
        self.assertFalse(degraded)
        self.assertIsNotNone(dets)
        # First wake: wave1 (no ped/face_id when cascade on)
        self.assertTrue(any("vehicles" in c or "objects" in c for c in calls))
        # Second wake: wave2 dependents
        self.assertTrue(
            any(c >= {"pedestrians", "face_id"} for c in calls),
            msg=f"calls={calls}",
        )


if __name__ == "__main__":
    unittest.main()
