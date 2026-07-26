"""
Orquestador foto-only: imagen local → detection/* → Adapter.

Flujo por foto:
  1. Poll GET /media/current (idle si no hay foto)
  2. cv2.imread
  3. Capacidades del registro (detection.registry); con
     ENABLE_EVIDENCE_CASCADE: oleada 1 → evidencia → oleada 2
     (pedestrians / face_id / open_vocab)
  4. merge COCO + attrs→person + extend/append según Cap.merge
  5. OCR de patente opcional sobre top-K vehicles
  6. overlay EN local → POST /preview/frame
  7. JSON → POST /ingest

Con ENABLE_CONTAINER_LIFECYCLE: pause idle de ped/face_id;
unpause al necesitarlos (oleada 2 o gather legacy).

Sin foto: idle. DEMO_MODE: detecciones sintéticas sin PaddleX.
No abre RTSP ni video.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Optional

import cv2
import httpx

from bridge.cascade import (
    CascadeConfig,
    decide_dependent_caps,
    dependent_names_from_decision,
    wave1_capability_names,
)
from bridge.lifecycle import (
    ContainerLifecycle,
    build_lifecycle_from_env,
)
from bridge.media import (
    MEDIA_DIR,
    resolve_active_source,
)
from detection.common.geometry import encode_jpeg, maybe_resize_for_infer, scale_detections
from detection.common.nms_cross_cap import apply_cross_cap_nms
from detection.common.preview import draw_preview
from detection.common.tiled_infer import ENABLE_INFER_TILING
from detection.common.zones import (
    absolute_polygons,
    load_zone_configs,
    tag_detections_with_zones,
)
from detection.objects import infer_objects_tiled_sync
from detection.plates import enrich_vehicles_with_plates
from detection.registry import (
    CAPABILITIES,
    Capability,
    attach_object_track_ids,
    capability_status_line,
    merge_coco_detections,
    merge_person_attributes,
    reset_all_trackers,
)
from detection.vehicles import infer_vehicles_tiled_sync

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] bridge: %(message)s",
)
logger = logging.getLogger("bridge")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

ADAPTER_INGEST_URL = os.getenv(
    "ADAPTER_INGEST_URL", "http://adapter:8000/ingest"
)
ADAPTER_MEDIA_CURRENT_URL = os.getenv(
    "ADAPTER_MEDIA_CURRENT_URL", "http://adapter:8000/media/current"
)
ADAPTER_PREVIEW_FRAME_URL = os.getenv(
    "ADAPTER_PREVIEW_FRAME_URL", "http://adapter:8000/preview/frame"
)
ADAPTER_CAPABILITIES_URL = os.getenv(
    "ADAPTER_CAPABILITIES_URL", "http://adapter:8000/capabilities"
)
MEDIA_POLL_INTERVAL = float(os.getenv("MEDIA_POLL_INTERVAL", "1.0"))
PREVIEW_IMAGE_HEARTBEAT_SECONDS = float(
    os.getenv("PREVIEW_IMAGE_HEARTBEAT_SECONDS", "5.0")
)
FPS = float(os.getenv("BRIDGE_FPS", "1"))
FRAME_INTERVAL = 1.0 / max(FPS, 0.1)
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))


def demo_detections() -> list[dict[str, Any]]:
    """Detecciones sintéticas para DEMO_MODE (sin imagen ni PaddleX)."""
    track_id = str(random.randint(1, 5))
    plates = ["ABC123", "ABC123", "ABG123", "XYZ789", "ABC123"]
    colors = ["white", "white", "silver", "black", "white"]
    return [
        {
            "track_id": track_id,
            "label": random.choice(["car", "truck", "bus"]),
            "score": round(random.uniform(0.6, 0.98), 3),
            "color": random.choice(colors),
            "bbox": [100, 120, 340, 280],
            "plate": {
                "text": random.choice(plates),
                "score": round(random.uniform(0.5, 0.97), 3),
            },
            "frame_ts": datetime.now(timezone.utc).isoformat(),
        }
    ]


async def post_json(client: httpx.AsyncClient, url: str, payload: Any) -> bool:
    """POST JSON; False ante fallo (loguea warning)."""
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("POST %s failed: %s", url, exc)
        return False


async def notify_degraded(client: httpx.AsyncClient) -> None:
    """Señala al adapter que el pipeline primario (vehicles) falló."""
    await post_json(client, ADAPTER_INGEST_URL, {"degraded": True})


async def fetch_current_media(client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    """GET /media/current. None si no hay foto o falla el poll."""
    try:
        resp = await client.get(ADAPTER_MEDIA_CURRENT_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Media poll failed: %s", exc)
        return None

    if not isinstance(data, dict) or not data.get("name"):
        return None
    return {
        "name": data["name"],
        "type": data.get("type") or "image",
        "generation": data.get("generation"),
    }


async def fetch_active_capability_names(client: httpx.AsyncClient) -> set[str]:
    """Registry names con active=true desde GET /capabilities.

    Fallback: todos los CAPABILITIES (comportamiento pre-Fase2) si falla el GET.
    """
    try:
        resp = await client.get(ADAPTER_CAPABILITIES_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Capabilities fetch failed; running all: %s", exc)
        return {cap.name for cap in CAPABILITIES}

    caps = data.get("capabilities") if isinstance(data, dict) else None
    if not isinstance(caps, dict):
        return {cap.name for cap in CAPABILITIES}

    names: set[str] = set()
    for entry in caps.values():
        if isinstance(entry, dict) and entry.get("active") and entry.get("name"):
            names.add(str(entry["name"]))
    return names


def filter_capabilities_for_gather(active_names: set[str]) -> list:
    """SPA-active + always vehicles + pedestrians (ENABLE short-circuits inside)."""
    return [
        cap
        for cap in CAPABILITIES
        if cap.name == "vehicles"
        or cap.name == "pedestrians"
        or cap.name in active_names
    ]


async def infer_capability(
    client: httpx.AsyncClient,
    cap: Capability,
    jpeg: bytes,
    frame_wh: tuple[int, int],
) -> Any:
    """Invoca una capacidad; el caller aísla fallos vía retorno None del client."""
    if cap.needs_frame_wh:
        return await cap.infer(client, jpeg, frame_wh=frame_wh)
    return await cap.infer(client, jpeg)


async def gather_capabilities(
    client: httpx.AsyncClient,
    caps: list[Capability],
    jpeg: bytes,
    frame_wh: tuple[int, int],
) -> dict[str, Any]:
    """asyncio.gather sobre caps; resultados keyed por name (orden de merge aparte)."""
    if not caps:
        return {}
    gathered = await asyncio.gather(
        *[infer_capability(client, cap, jpeg, frame_wh) for cap in caps]
    )
    return {cap.name: result for cap, result in zip(caps, gathered)}


async def push_preview_frame(client: httpx.AsyncClient, jpeg: bytes) -> None:
    """POST JPEG anotado a /preview/frame. Falla en silencio."""
    try:
        resp = await client.post(
            ADAPTER_PREVIEW_FRAME_URL,
            content=jpeg,
            headers={"Content-Type": "image/jpeg"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.debug("Preview push failed: %s", exc)


async def run_detections(
    client: httpx.AsyncClient,
    frame_hires,
    *,
    lifecycle: Optional[ContainerLifecycle] = None,
) -> tuple[Optional[list[dict[str, Any]]], bool, Optional[bytes]]:
    """Orquesta el registro de capacidades + plates + preview.

    Returns:
        (detections, degraded, preview_jpeg).
        detections is None = saltar (encode/vehicles falló).
        Capacidades opcionales no degradan el bridge.

    Invariante coords: cada capacidad entrega cajas en hires antes de merge.
    Con ENABLE_INFER_TILING, vehicles/objects usan slicer sobre hires (sin
    scale_detections). Caps no tileadas escalan en su rama con scale_*.

    Con ENABLE_EVIDENCE_CASCADE: oleada 1 (core + independientes) → evidencia
    → oleada 2 (pedestrians / face_id / open_vocab). Sin flag: gather único.

    Con ENABLE_CONTAINER_LIFECYCLE: unpause ped/face_id antes de invocarlos.
    """
    frame_infer, scale_x, scale_y = maybe_resize_for_infer(frame_hires)
    jpeg = encode_jpeg(frame_infer)
    if jpeg is None:
        return None, False, None

    h, w = frame_hires.shape[:2]
    frame_wh = (w, h)

    active_names = await fetch_active_capability_names(client)
    caps = filter_capabilities_for_gather(active_names)
    cascade_cfg = CascadeConfig.from_env()
    tiling = ENABLE_INFER_TILING
    # Tiled caps run via to_thread on hires; exclude from JPEG gather.
    tiled_names = {"vehicles", "objects"} if tiling else set()
    want_objects = any(c.name == "objects" for c in caps)

    eligible_names = {c.name for c in caps}
    wave1_names = wave1_capability_names(
        eligible_names, cascade_enabled=cascade_cfg.enabled
    )
    caps_wave1 = [c for c in caps if c.name in wave1_names]
    caps_gather_w1 = [c for c in caps_wave1 if c.name not in tiled_names]

    # Wake pausables that land in wave1 (cascade off, or future pausables).
    if lifecycle is not None and lifecycle.enabled:
        await lifecycle.ensure_awake(wave1_names)

    by_name = await gather_capabilities(
        client, caps_gather_w1, jpeg, frame_wh
    )

    if tiling:
        vehicle_detections = await asyncio.to_thread(
            infer_vehicles_tiled_sync, frame_hires
        )
    else:
        vehicle_detections = by_name.get("vehicles")
        if vehicle_detections is not None:
            scale_detections(vehicle_detections, scale_x, scale_y)

    if vehicle_detections is None:
        await notify_degraded(client)
        return None, True, None

    if tiling and want_objects:
        object_raw = await asyncio.to_thread(
            infer_objects_tiled_sync, frame_hires
        )
    else:
        object_raw = by_name.get("objects")
        if object_raw:
            scale_detections(object_raw, scale_x, scale_y)

    if cascade_cfg.enabled:
        decision = decide_dependent_caps(
            config=cascade_cfg,
            objects_active=want_objects,
            object_raw=object_raw,
            faces_raw=by_name.get("faces"),
            open_vocab_in_gather="open_vocab" in eligible_names,
            pedestrians_in_gather="pedestrians" in eligible_names,
            face_id_in_gather="face_id" in eligible_names,
        )
        dep_names = dependent_names_from_decision(decision)
        # Registry order for deterministic wave2.
        caps_wave2 = [c for c in caps if c.name in dep_names]
        logger.info(
            "cascade wave2=%s reasons=%s",
            sorted(dep_names),
            ",".join(decision.reasons),
        )
        if lifecycle is not None and lifecycle.enabled and dep_names:
            woken = await lifecycle.ensure_awake(dep_names)
            if woken:
                logger.info("lifecycle wake wave2=%s", sorted(woken))
        wave2 = await gather_capabilities(client, caps_wave2, jpeg, frame_wh)
        by_name.update(wave2)
    else:
        logger.debug("cascade disabled; single gather")

    # Merge loop: all non-tiled eligible caps (incl. wave2 dependents).
    caps_gather = [c for c in caps if c.name not in tiled_names]

    if object_raw:
        object_detections = attach_object_track_ids(object_raw)
        object_detections = merge_coco_detections(
            vehicle_detections, object_detections
        )
    else:
        object_detections = []

    ped_attrs = by_name.get("pedestrians")
    if ped_attrs:
        scale_detections(ped_attrs, scale_x, scale_y)
        object_detections = merge_person_attributes(object_detections, ped_attrs)

    detections: list[dict[str, Any]] = list(vehicle_detections) + list(
        object_detections
    )

    for cap in caps_gather:
        if cap.merge == "extend_scaled":
            dets = by_name.get(cap.name)
            if dets:
                scale_detections(dets, scale_x, scale_y)
                detections.extend(dets)
        elif cap.merge == "append_one":
            one = by_name.get(cap.name)
            if one is not None:
                detections.append(one)

    # Plate OCR remains ENABLE-only enrich (unchanged); not SPA-gated.
    await enrich_vehicles_with_plates(
        client, frame_hires, vehicle_detections, encode_jpeg
    )

    # NMS-B cross-cap (capa B): entity_type via class_id_for_cross_cap_nms.
    detections = apply_cross_cap_nms(detections)

    zone_cfgs = load_zone_configs()
    detections = tag_detections_with_zones(detections, frame_wh, zone_cfgs)
    zone_polys = absolute_polygons(zone_cfgs, frame_wh) if zone_cfgs else None

    preview_jpeg = draw_preview(
        frame_hires, detections, zone_polygons=zone_polys
    )
    return detections, False, preview_jpeg


async def run_image_source(
    client: httpx.AsyncClient,
    path: str,
    selected_name: Optional[str],
    generation: Any = None,
    *,
    lifecycle: Optional[ContainerLifecycle] = None,
) -> None:
    """Single-shot sobre una foto: infer + heartbeat preview hasta clear/cambio."""
    reset_all_trackers()

    frame_hires = cv2.imread(path)
    if frame_hires is None:
        raise RuntimeError(f"Cannot read image source: {path}")

    detections, _degraded, preview_jpeg = await run_detections(
        client, frame_hires, lifecycle=lifecycle
    )
    detections = detections or []
    # Always ingest (including []) so last_ingest_generation advances.
    await post_json(
        client,
        ADAPTER_INGEST_URL,
        {"detections": detections, "trace_id": generation},
    )

    if preview_jpeg is not None:
        await push_preview_frame(client, preview_jpeg)
    else:
        logger.warning(
            "Image source %s: sin preview (encode overlay falló)",
            path,
        )
    logger.info("Image source ready: %s detections=%d", path, len(detections))

    last_heartbeat = time.monotonic()
    while True:
        await asyncio.sleep(MEDIA_POLL_INTERVAL)
        polled = await fetch_current_media(client)
        if polled is None:
            logger.info("Media cleared -> leave image source (%s)", selected_name)
            return
        if polled.get("name") != selected_name:
            logger.info("Media selection changed away from image -> %s", polled)
            return
        if polled.get("generation") != generation:
            logger.info(
                "Generation changed %s -> %s; re-run analysis",
                generation,
                polled.get("generation"),
            )
            return

        now = time.monotonic()
        if (
            preview_jpeg is not None
            and now - last_heartbeat >= PREVIEW_IMAGE_HEARTBEAT_SECONDS
        ):
            await push_preview_frame(client, preview_jpeg)
            last_heartbeat = now


async def run_loop() -> None:
    """Loop principal: idle / demo / foto activa."""
    lifecycle = build_lifecycle_from_env()
    logger.info(
        "Bridge start (photo-only) media_dir=%s %s adapter=%s demo=%s "
        "lifecycle=%s idle_pause_s=%s pausable=%s",
        MEDIA_DIR,
        capability_status_line(),
        ADAPTER_INGEST_URL,
        DEMO_MODE,
        lifecycle.enabled,
        lifecycle.config.idle_pause_s if lifecycle.enabled else "-",
        sorted(lifecycle.config.cap_containers) if lifecycle.enabled else [],
    )

    idle_task: Optional[asyncio.Task] = None
    if lifecycle.enabled:
        started = await lifecycle.pause_all_pausable()
        if started:
            logger.info("lifecycle pause on start: %s", sorted(started))

        async def _idle_sweeper() -> None:
            # Poll often enough vs idle_pause_s without busy-looping.
            interval = min(30.0, max(5.0, lifecycle.config.idle_pause_s / 4.0))
            while True:
                await asyncio.sleep(interval)
                try:
                    paused = await lifecycle.pause_idle()
                    if paused:
                        logger.info("lifecycle pause idle: %s", sorted(paused))
                except Exception as exc:
                    logger.warning("lifecycle idle sweep failed: %s", exc)

        idle_task = asyncio.create_task(_idle_sweeper(), name="lifecycle-idle")

    selected: Optional[dict[str, Any]] = None

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            while True:
                try:
                    if DEMO_MODE:
                        detections = demo_detections()
                        await post_json(
                            client, ADAPTER_INGEST_URL, {"detections": detections}
                        )
                        await asyncio.sleep(FRAME_INTERVAL)
                        continue

                    polled = await fetch_current_media(client)
                    selected = polled if polled is not None else None

                    source = resolve_active_source(selected)
                    if source is None:
                        await asyncio.sleep(MEDIA_POLL_INTERVAL)
                        continue

                    await run_image_source(
                        client,
                        source,
                        selected.get("name") if selected else None,
                        selected.get("generation") if selected else None,
                        lifecycle=lifecycle if lifecycle.enabled else None,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("Bridge error on image source: %s", exc)
                    await asyncio.sleep(MEDIA_POLL_INTERVAL)
    finally:
        if idle_task is not None:
            idle_task.cancel()
            try:
                await idle_task
            except asyncio.CancelledError:
                pass
        await lifecycle.aclose()


def main() -> None:
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        logger.info("Bridge stopped")


if __name__ == "__main__":
    main()
