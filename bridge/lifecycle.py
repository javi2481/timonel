"""Ciclo de vida Docker para capacidades pausables (Fase 2).

Pausa contenedores extended exclusivos de oleada 2 tras idle;
unpause justo antes de invocarlos. No libera RAM (solo CPU).

MVP pausable: pedestrians, face_id.
open_vocab NO se pausa: comparte tm-paddlex-open-vocab con signs (oleada 1).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

logger = logging.getLogger("bridge")


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


# Capacidad → container_name (compose). Solo wave2-exclusivos en MVP.
DEFAULT_PAUSABLE_CAP_CONTAINERS: dict[str, str] = {
    "pedestrians": "tm-paddlex-pedestrians",
    "face_id": "tm-paddlex-face-id",
}


@dataclass(frozen=True)
class LifecycleConfig:
    enabled: bool
    idle_pause_s: float
    docker_sock: str
    cap_containers: dict[str, str]

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
                elif part in DEFAULT_PAUSABLE_CAP_CONTAINERS:
                    mapping[part] = DEFAULT_PAUSABLE_CAP_CONTAINERS[part]
            cap_containers = mapping
        else:
            cap_containers = dict(DEFAULT_PAUSABLE_CAP_CONTAINERS)

        return cls(
            enabled=_env_bool("ENABLE_CONTAINER_LIFECYCLE", "false"),
            idle_pause_s=float(os.getenv("CONTAINER_IDLE_PAUSE_S", "120")),
            docker_sock=os.getenv("DOCKER_SOCK", "/var/run/docker.sock"),
            cap_containers=cap_containers,
        )


class DockerEngine(Protocol):
    async def container_state(self, name: str) -> Optional[str]:
        """Return Status string (running/paused/exited/…) or None if missing."""

    async def pause(self, name: str) -> bool:
        ...

    async def unpause(self, name: str) -> bool:
        ...

    async def aclose(self) -> None:
        ...


class HttpDockerEngine:
    """Docker Engine API over unix socket (no docker CLI / SDK)."""

    def __init__(self, sock_path: str, *, timeout: float = 10.0) -> None:
        import httpx

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

    async def pause(self, name: str) -> bool:
        client = await self._get_client()
        try:
            resp = await client.post(f"/containers/{name}/pause")
        except Exception as exc:
            logger.warning("docker pause %s failed: %s", name, exc)
            return False
        # 204 success; 304/409 already paused — treat as ok.
        if resp.status_code in (204, 304) or resp.status_code == 409:
            return True
        if resp.status_code >= 400:
            logger.warning(
                "docker pause %s status=%s body=%s",
                name,
                resp.status_code,
                resp.text[:200],
            )
            return False
        return True

    async def unpause(self, name: str) -> bool:
        client = await self._get_client()
        try:
            resp = await client.post(f"/containers/{name}/unpause")
        except Exception as exc:
            logger.warning("docker unpause %s failed: %s", name, exc)
            return False
        if resp.status_code in (204, 304) or resp.status_code == 409:
            return True
        if resp.status_code >= 400:
            logger.warning(
                "docker unpause %s status=%s body=%s",
                name,
                resp.status_code,
                resp.text[:200],
            )
            return False
        return True


@dataclass
class ContainerLifecycle:
    """Track last-use and pause/unpause pausable capability containers."""

    config: LifecycleConfig
    engine: DockerEngine
    _last_used: dict[str, float] = field(default_factory=dict)
    _paused: set[str] = field(default_factory=set)

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

    async def ensure_awake(self, cap_names: Any) -> list[str]:
        """Unpause containers for the given capability names. Returns woken caps."""
        if not self.enabled:
            return []
        woken: list[str] = []
        for cap in sorted(set(cap_names)):
            cname = self.config.cap_containers.get(cap)
            if not cname:
                continue
            state = await self.engine.container_state(cname)
            if state is None:
                logger.warning("lifecycle: container missing for %s (%s)", cap, cname)
                continue
            if state == "paused":
                ok = await self.engine.unpause(cname)
                if ok:
                    logger.info("lifecycle unpause %s (%s)", cname, cap)
                    woken.append(cap)
                    self._paused.discard(cap)
                else:
                    logger.warning("lifecycle unpause failed %s (%s)", cname, cap)
            elif state != "running":
                logger.warning(
                    "lifecycle: %s (%s) status=%s (expected running/paused)",
                    cname,
                    cap,
                    state,
                )
            self.touch([cap])
        return woken

    async def pause_idle(self, *, now: Optional[float] = None) -> list[str]:
        """Pause pausables idle longer than idle_pause_s. Returns paused caps."""
        if not self.enabled:
            return []
        now = time.monotonic() if now is None else now
        idle_s = max(0.0, self.config.idle_pause_s)
        paused: list[str] = []
        for cap, cname in self.config.cap_containers.items():
            last = self._last_used.get(cap)
            # Never used this process → treat as idle since epoch 0 of monotonic
            # only after we've observed them; use -inf so they pause on first sweep.
            if last is None:
                age = idle_s + 1.0
            else:
                age = now - last
            if age < idle_s:
                continue
            state = await self.engine.container_state(cname)
            if state is None:
                continue
            if state == "paused":
                self._paused.add(cap)
                continue
            if state != "running":
                continue
            ok = await self.engine.pause(cname)
            if ok:
                logger.info(
                    "lifecycle pause %s (%s) idle=%.0fs",
                    cname,
                    cap,
                    age if last is not None else -1,
                )
                paused.append(cap)
                self._paused.add(cap)
        return paused

    async def pause_all_pausable(self) -> list[str]:
        """Startup: pause every configured pausable that is running."""
        if not self.enabled:
            return []
        # Force idle by clearing last_used and setting idle threshold bypass.
        self._last_used.clear()
        return await self.pause_idle(now=time.monotonic() + self.config.idle_pause_s + 1.0)

    async def aclose(self) -> None:
        await self.engine.aclose()


def build_lifecycle_from_env() -> ContainerLifecycle:
    cfg = LifecycleConfig.from_env()
    engine = HttpDockerEngine(cfg.docker_sock)
    return ContainerLifecycle(config=cfg, engine=engine)


__all__ = [
    "ContainerLifecycle",
    "DEFAULT_PAUSABLE_CAP_CONTAINERS",
    "DockerEngine",
    "HttpDockerEngine",
    "LifecycleConfig",
    "build_lifecycle_from_env",
]
