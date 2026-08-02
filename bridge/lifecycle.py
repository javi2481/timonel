"""Ciclo de vida Docker para capacidades extended (override ondemand).

Start/stop (libera RAM) de contenedores extended tras idle;
start + wait health justo antes de invocarlos.
Requiere ENABLE_CONTAINER_LIFECYCLE + compose.ondemand.yml.

Objects, faces, pose, text/ocr, vehicles NO entran en este mapa
(siempre up en el stack default / full_up).
open_vocab y signs comparten tm-paddlex-open-vocab.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

import httpx

logger = logging.getLogger("bridge")


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


# Capacidad registry → container_name (solo extended; lifecycle opt-in).
DEFAULT_ONDEMAND_CAP_CONTAINERS: dict[str, str] = {
    "pedestrians": "tm-paddlex-pedestrians",
    "face_id": "tm-paddlex-face-id",
    "scene": "tm-paddlex-scene",
    "scene_cls": "tm-paddlex-scene-cls",
    "instances": "tm-paddlex-instances",
    "small_objects": "tm-paddlex-small-objects",
    "anomaly": "tm-paddlex-anomaly",
    "open_vocab": "tm-paddlex-open-vocab",
    "signs": "tm-paddlex-open-vocab",
}

# Shared container: do not stop if another mapped cap is still "in use".
_SHARED_CONTAINERS: dict[str, frozenset[str]] = {
    "tm-paddlex-open-vocab": frozenset({"open_vocab", "signs"}),
}

# registry name → health base URL env (docs/openapi).
_CAP_HEALTH_ENV: dict[str, str] = {
    "pedestrians": "PADDLEX_PEDESTRIANS_URL",
    "face_id": "PADDLEX_FACE_ID_URL",
    "scene": "PADDLEX_SCENE_URL",
    "scene_cls": "PADDLEX_SCENE_CLS_URL",
    "instances": "PADDLEX_INSTANCES_URL",
    "small_objects": "PADDLEX_SMALL_OBJECTS_URL",
    "anomaly": "PADDLEX_ANOMALY_URL",
    "open_vocab": "PADDLEX_OPEN_VOCAB_URL",
    "signs": "PADDLEX_SIGNS_OV_URL",
}

# Keep old name as alias for env parsing / tests.
DEFAULT_PAUSABLE_CAP_CONTAINERS = DEFAULT_ONDEMAND_CAP_CONTAINERS


@dataclass(frozen=True)
class LifecycleConfig:
    enabled: bool
    idle_pause_s: float
    docker_sock: str
    cap_containers: dict[str, str]
    health_timeout_s: float
    health_poll_s: float

    @classmethod
    def from_env(cls) -> LifecycleConfig:
        raw = os.getenv("LIFECYCLE_PAUSE_CAPS", "").strip()
        if raw:
            mapping: dict[str, str] = {}
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                if "=" in part:
                    cap, cname = part.split("=", 1)
                    mapping[cap.strip()] = cname.strip()
                elif part in DEFAULT_ONDEMAND_CAP_CONTAINERS:
                    mapping[part] = DEFAULT_ONDEMAND_CAP_CONTAINERS[part]
            cap_containers = mapping
        else:
            cap_containers = dict(DEFAULT_ONDEMAND_CAP_CONTAINERS)

        return cls(
            enabled=_env_bool("ENABLE_CONTAINER_LIFECYCLE", "false"),
            idle_pause_s=float(os.getenv("CONTAINER_IDLE_PAUSE_S", "120")),
            docker_sock=os.getenv("DOCKER_SOCK", "/var/run/docker.sock"),
            cap_containers=cap_containers,
            health_timeout_s=float(os.getenv("CONTAINER_HEALTH_TIMEOUT_S", "300")),
            health_poll_s=float(os.getenv("CONTAINER_HEALTH_POLL_S", "2")),
        )


class DockerEngine(Protocol):
    async def container_state(self, name: str) -> Optional[str]:
        """Return Status string (running/paused/exited/…) or None if missing."""

    async def pause(self, name: str) -> bool:
        ...

    async def unpause(self, name: str) -> bool:
        ...

    async def start(self, name: str) -> bool:
        ...

    async def stop(self, name: str) -> bool:
        ...

    async def aclose(self) -> None:
        ...


class HttpDockerEngine:
    """Docker Engine API over unix socket (no docker CLI / SDK)."""

    def __init__(self, sock_path: str, *, timeout: float = 30.0) -> None:
        self._httpx = httpx
        self._sock = sock_path
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self):
        if self._client is None:
            transport = self._httpx.AsyncHTTPTransport(uds=self._sock)
            self._client = self._httpx.AsyncClient(
                transport=transport,
                base_url="http://docker",
                timeout=self._timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def container_state(self, name: str) -> Optional[str]:
        client = await self._get_client()
        try:
            resp = await client.get(f"/containers/{name}/json")
        except Exception as exc:
            logger.warning("docker inspect %s failed: %s", name, exc)
            return None
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            logger.warning(
                "docker inspect %s status=%s body=%s",
                name,
                resp.status_code,
                resp.text[:200],
            )
            return None
        data = resp.json()
        state = data.get("State") if isinstance(data, dict) else None
        if not isinstance(state, dict):
            return None
        status = str(state.get("Status") or "").strip().lower()
        return status or None

    async def _post_action(self, name: str, action: str) -> bool:
        client = await self._get_client()
        try:
            resp = await client.post(f"/containers/{name}/{action}")
        except Exception as exc:
            logger.warning("docker %s %s failed: %s", action, name, exc)
            return False
        # 204 success; 304/409 already in desired state — treat as ok.
        if resp.status_code in (204, 304) or resp.status_code == 409:
            return True
        if resp.status_code >= 400:
            logger.warning(
                "docker %s %s status=%s body=%s",
                action,
                name,
                resp.status_code,
                resp.text[:200],
            )
            return False
        return True

    async def pause(self, name: str) -> bool:
        return await self._post_action(name, "pause")

    async def unpause(self, name: str) -> bool:
        return await self._post_action(name, "unpause")

    async def start(self, name: str) -> bool:
        return await self._post_action(name, "start")

    async def stop(self, name: str) -> bool:
        return await self._post_action(name, "stop")


async def _wait_http_healthy(base_url: str, *, timeout_s: float, poll_s: float) -> bool:
    base = base_url.rstrip("/")
    deadline = time.monotonic() + max(1.0, timeout_s)
    paths = ("/docs", "/openapi.json", "/health")
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            for path in paths:
                try:
                    resp = await client.get(f"{base}{path}")
                    if resp.status_code < 500:
                        return True
                except Exception:
                    pass
            await asyncio.sleep(max(0.2, poll_s))
    return False


@dataclass
class ContainerLifecycle:
    """Track last-use; start/stop extended caps (lifecycle opt-in)."""

    config: LifecycleConfig
    engine: DockerEngine
    _last_used: dict[str, float] = field(default_factory=dict)
    _stopped: set[str] = field(default_factory=set)
    # cap → last ensure_awake error message (empty if ok)
    last_errors: dict[str, str] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return self.config.enabled and bool(self.config.cap_containers)

    def container_for(self, cap_name: str) -> Optional[str]:
        return self.config.cap_containers.get(cap_name)

    def touch(self, cap_names: Any) -> None:
        now = time.monotonic()
        for name in cap_names:
            if name in self.config.cap_containers:
                self._last_used[name] = now

    def _health_url_for(self, cap: str) -> Optional[str]:
        env_key = _CAP_HEALTH_ENV.get(cap)
        if not env_key:
            return None
        return os.getenv(env_key) or None

    async def ensure_awake(self, cap_names: Any) -> list[str]:
        """Start/unpause containers; wait health. Returns woken caps."""
        if not self.enabled:
            return []
        woken: list[str] = []
        for cap in sorted(set(cap_names)):
            cname = self.config.cap_containers.get(cap)
            if not cname:
                continue
            state = await self.engine.container_state(cname)
            if state is None:
                msg = f"container missing: {cname}"
                logger.warning("lifecycle: %s (%s)", msg, cap)
                self.last_errors[cap] = msg
                continue

            started = False
            if state == "paused":
                ok = await self.engine.unpause(cname)
                if not ok:
                    self.last_errors[cap] = f"unpause failed: {cname}"
                    continue
                started = True
            elif state in ("exited", "created", "dead"):
                ok = await self.engine.start(cname)
                if not ok:
                    self.last_errors[cap] = f"start failed: {cname}"
                    continue
                started = True
            elif state != "running":
                msg = f"unexpected status={state} for {cname}"
                logger.warning("lifecycle: %s (%s)", msg, cap)
                self.last_errors[cap] = msg
                continue

            # Touch before health wait so idle sweeper does not stop a warming container.
            self.touch([cap])
            self._stopped.discard(cap)

            health_url = self._health_url_for(cap)
            if health_url:
                healthy = await _wait_http_healthy(
                    health_url,
                    timeout_s=self.config.health_timeout_s,
                    poll_s=self.config.health_poll_s,
                )
                if not healthy:
                    msg = f"health timeout: {health_url}"
                    logger.warning("lifecycle: %s (%s)", msg, cap)
                    self.last_errors[cap] = msg
                    continue

            self.last_errors.pop(cap, None)
            if started:
                logger.info("lifecycle start/awake %s (%s)", cname, cap)
                woken.append(cap)
            self.touch([cap])
        return woken

    def _caps_sharing_container(self, cname: str) -> frozenset[str]:
        shared = _SHARED_CONTAINERS.get(cname)
        if shared:
            return shared
        return frozenset(
            cap for cap, cn in self.config.cap_containers.items() if cn == cname
        )

    async def stop_idle(self, *, now: Optional[float] = None) -> list[str]:
        """Stop extended containers idle longer than idle_pause_s. Returns stopped caps."""
        if not self.enabled:
            return []
        now = time.monotonic() if now is None else now
        idle_s = max(0.0, self.config.idle_pause_s)
        stopped: list[str] = []
        # Deduplicate by container so shared OV is stopped once.
        seen_containers: set[str] = set()
        for cap, cname in self.config.cap_containers.items():
            if cname in seen_containers:
                continue
            siblings = self._caps_sharing_container(cname)
            # Any sibling recently used → keep running
            keep = False
            ages: list[float] = []
            for sib in siblings:
                if sib not in self.config.cap_containers:
                    continue
                last = self._last_used.get(sib)
                if last is None:
                    ages.append(idle_s + 1.0)
                else:
                    age = now - last
                    ages.append(age)
                    if age < idle_s:
                        keep = True
            if keep:
                continue
            age = max(ages) if ages else idle_s + 1.0
            state = await self.engine.container_state(cname)
            if state is None:
                continue
            if state in ("exited", "created", "dead"):
                for sib in siblings:
                    if sib in self.config.cap_containers:
                        self._stopped.add(sib)
                seen_containers.add(cname)
                continue
            if state == "paused":
                # Prefer stop to free RAM
                await self.engine.unpause(cname)
            if state not in ("running", "paused"):
                continue
            ok = await self.engine.stop(cname)
            if ok:
                logger.info(
                    "lifecycle stop %s idle=%.0fs caps=%s",
                    cname,
                    age,
                    sorted(siblings & set(self.config.cap_containers)),
                )
                for sib in siblings:
                    if sib in self.config.cap_containers:
                        stopped.append(sib)
                        self._stopped.add(sib)
                seen_containers.add(cname)
        return stopped

    async def pause_idle(self, *, now: Optional[float] = None) -> list[str]:
        """Alias: stop_idle (RAM-freeing). Kept for callers/tests naming."""
        return await self.stop_idle(now=now)

    async def pause_all_pausable(self) -> list[str]:
        """Startup: stop every configured lifecycle container that is running."""
        if not self.enabled:
            return []
        self._last_used.clear()
        return await self.stop_idle(now=time.monotonic() + self.config.idle_pause_s + 1.0)

    async def aclose(self) -> None:
        await self.engine.aclose()


def build_lifecycle_from_env() -> ContainerLifecycle:
    cfg = LifecycleConfig.from_env()
    engine = HttpDockerEngine(cfg.docker_sock)
    return ContainerLifecycle(config=cfg, engine=engine)


__all__ = [
    "ContainerLifecycle",
    "DEFAULT_ONDEMAND_CAP_CONTAINERS",
    "DEFAULT_PAUSABLE_CAP_CONTAINERS",
    "DockerEngine",
    "HttpDockerEngine",
    "LifecycleConfig",
    "build_lifecycle_from_env",
]
