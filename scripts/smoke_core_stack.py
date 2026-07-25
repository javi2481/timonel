#!/usr/bin/env python3
"""Smoke integración Core: media/select → bridge → /events → preview.

Cierra el gap que eval_paddlex_fixtures no cubre (merge, epp_core, preview).

Uso (compose up; default fo_vehicles_0002 + fo_objects_0001):

    python scripts/smoke_core_stack.py
    EXPECT_PLATE_OCR=true python scripts/smoke_core_stack.py   # si OCR on en el stack

Exit 0 solo si todos los asserts pasan.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

ADAPTER = os.getenv("ADAPTER_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SEC = float(os.getenv("SMOKE_TIMEOUT_SEC", "90"))
POLL_SEC = float(os.getenv("SMOKE_POLL_SEC", "2"))
# Placeholder adapter/ui/placeholder_preview.jpg ≈ 9671 bytes.
PREVIEW_MIN_BYTES = int(os.getenv("SMOKE_PREVIEW_MIN_BYTES", "12000"))
EXPECT_PLATE_OCR = os.getenv("EXPECT_PLATE_OCR", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
# fo_vehicles_0001 suele dar 0 boxes en PP-YOLOE local; 0002 tiene hits estables.
VEHICLES_PHOTO = os.getenv("SMOKE_VEHICLES_PHOTO", "fo_vehicles_0002.jpg")
OBJECTS_PHOTO = os.getenv("SMOKE_OBJECTS_PHOTO", "fo_objects_0001.jpg")
# Si true (default): PUT /capabilities con solo vehicle+object activos (Core).
PIN_CORE_CAPS = os.getenv("SMOKE_PIN_CORE_CAPS", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)

VEHICLE_COCO = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})
IOU_DUP = 0.5
CORE_ACTIVE = {
    "vehicle": True,
    "object": True,
    "face": False,
    "scene": False,
    "pose": False,
    "text": False,
    "face_id": False,
    "sign": False,
    "scene_cls": False,
    "instance": False,
    "small_object": False,
    "anomaly": False,
    "open_vocab": False,
}


class SmokeFail(Exception):
    """Assert de smoke fallido."""


def _env_bool_label() -> str:
    return "on" if EXPECT_PLATE_OCR else "off"


def http_json(method: str, path: str, body: Optional[dict] = None) -> Any:
    url = f"{ADAPTER}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SmokeFail(f"adapter unreachable ({url}): {exc}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SmokeFail(f"HTTP {exc.code} {url}: {detail}") from exc


def http_bytes(path: str) -> bytes:
    url = f"{ADAPTER}{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise SmokeFail(f"adapter unreachable ({url}): {exc}") from exc
    except urllib.error.HTTPError as exc:
        raise SmokeFail(f"HTTP {exc.code} {url}") from exc


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a[:4]
    bx1, by1, bx2, by2 = b[:4]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def wait_ingest_complete() -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_SEC
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = http_json("GET", "/events?limit=100") or {}
        gen = last.get("generation")
        last_ingest = last.get("last_ingest_generation")
        if gen is not None and last_ingest is not None and int(gen) == int(last_ingest):
            return last
        time.sleep(POLL_SEC)
    raise SmokeFail(
        f"timeout {TIMEOUT_SEC}s esperando generation==last_ingest_generation "
        f"(last generation={last.get('generation')!r}, "
        f"last_ingest={last.get('last_ingest_generation')!r})"
    )


def _bbox(payload: dict[str, Any]) -> Optional[list[float]]:
    bb = payload.get("bbox")
    if isinstance(bb, list) and len(bb) >= 4:
        try:
            return [float(x) for x in bb[:4]]
        except (TypeError, ValueError):
            return None
    return None


def assert_common_schema(events: list[dict[str, Any]], label: str) -> None:
    if not events:
        raise SmokeFail(f"{label}: events vacio tras ingest completo")
    for i, ev in enumerate(events):
        if ev.get("schema_version") != "1.0":
            raise SmokeFail(f"{label}[{i}]: schema_version!=1.0 ({ev.get('schema_version')!r})")
        conf = ev.get("confidence")
        try:
            c = float(conf)
        except (TypeError, ValueError) as exc:
            raise SmokeFail(f"{label}[{i}]: confidence invalido {conf!r}") from exc
        if not 0.0 <= c <= 1.0:
            raise SmokeFail(f"{label}[{i}]: confidence fuera de [0,1]: {c}")


def assert_vehicles(payload_events: list[dict[str, Any]]) -> None:
    vehicles = [e for e in payload_events if e.get("entity_type") == "vehicle"]
    if not vehicles:
        raise SmokeFail("vehicles: ningun entity_type=vehicle")

    typed = 0
    for i, ev in enumerate(vehicles):
        p = ev.get("payload") or {}
        bb = _bbox(p)
        if bb is None:
            raise SmokeFail(f"vehicles[{i}]: bbox ausente o invalido")
        vt = p.get("vehicle_type")
        if isinstance(vt, str) and vt.strip():
            typed += 1
    if typed < 1:
        raise SmokeFail("vehicles: ningun payload.vehicle_type no vacio")

    # Anti-doble merge_coco: object COCO vehicle-class solapando un vehicle.
    objects = [e for e in payload_events if e.get("entity_type") == "object"]
    for oi, oev in enumerate(objects):
        op = oev.get("payload") or {}
        cname = (op.get("class_name") or "").strip().lower()
        if cname not in VEHICLE_COCO:
            continue
        ob = _bbox(op)
        if ob is None:
            continue
        for vi, vev in enumerate(vehicles):
            vb = _bbox(vev.get("payload") or {})
            if vb is None:
                continue
            if iou(ob, vb) > IOU_DUP:
                raise SmokeFail(
                    f"anti-doble: object[{oi}] class={cname} IoU>{IOU_DUP} "
                    f"con vehicle[{vi}] (sospecha merge_coco/escala)"
                )

    plates = [
        (e.get("payload") or {}).get("plate_text")
        for e in vehicles
        if (e.get("payload") or {}).get("plate_text")
    ]
    plates_nonempty = [p for p in plates if isinstance(p, str) and p.strip()]
    if EXPECT_PLATE_OCR:
        if not plates_nonempty:
            raise SmokeFail(
                "EXPECT_PLATE_OCR=true pero ningun vehicle.payload.plate_text"
            )
    else:
        if plates_nonempty:
            raise SmokeFail(
                "EXPECT_PLATE_OCR=false pero hay plate_text="
                f"{plates_nonempty!r} (ENABLE_PLATE_OCR encendido?)"
            )


def assert_objects(payload_events: list[dict[str, Any]]) -> None:
    objects = [e for e in payload_events if e.get("entity_type") == "object"]
    if not objects:
        raise SmokeFail("objects: ningun entity_type=object")
    named = 0
    for i, ev in enumerate(objects):
        p = ev.get("payload") or {}
        bb = _bbox(p)
        if bb is None:
            raise SmokeFail(f"objects[{i}]: bbox ausente o invalido")
        cn = p.get("class_name")
        if isinstance(cn, str) and cn.strip():
            named += 1
    if named < 1:
        raise SmokeFail("objects: ningun payload.class_name no vacio")


def assert_preview() -> None:
    body = http_bytes("/preview.jpg")
    n = len(body)
    if n < PREVIEW_MIN_BYTES:
        raise SmokeFail(
            f"preview.jpg demasiado chico ({n} B < {PREVIEW_MIN_BYTES}); "
            "probable placeholder (~9.6 KB) o bridge sin draw_preview"
        )


def pin_core_capabilities() -> None:
    """Deja solo vehicle+object activos para no mezclar ruido extended."""
    print("== PUT /capabilities Core-only ==")
    body = http_json("PUT", "/capabilities", {"active": CORE_ACTIVE})
    if not isinstance(body, dict) or "capabilities" not in body:
        raise SmokeFail(f"capabilities PUT fallo: {body!r}")
    caps = body["capabilities"]
    active = {k: v.get("active") for k, v in caps.items()}
    if not active.get("vehicle") or not active.get("object"):
        raise SmokeFail(f"vehicle/object deben quedar active: {active}")
    extras = [k for k, v in active.items() if k not in ("vehicle", "object") and v]
    if extras:
        raise SmokeFail(f"caps extra siguen active: {extras}")
    print(f"  generation={body.get('generation')} active={{vehicle,object}}")


def run_photo(name: str, kind: str) -> None:
    print(f"== select {name} ==")
    sel = http_json("POST", "/media/select", {"name": name})
    if not isinstance(sel, dict) or not sel.get("ok"):
        raise SmokeFail(f"media/select fallo para {name}: {sel!r}")
    print(f"  generation={sel.get('generation')}")

    print(f"== wait ingest ({kind}) ==")
    data = wait_ingest_complete()
    events = list(data.get("events") or [])
    print(
        f"  generation={data.get('generation')} "
        f"events={len(events)} degraded={data.get('degraded')}"
    )

    assert_common_schema(events, kind)
    if kind == "vehicles":
        assert_vehicles(events)
    else:
        assert_objects(events)

    print(f"== preview after {kind} ==")
    assert_preview()
    print(f"  PASS {kind}")


def main() -> int:
    print(
        f"ADAPTER={ADAPTER} EXPECT_PLATE_OCR={_env_bool_label()} "
        f"photos={VEHICLES_PHOTO},{OBJECTS_PHOTO}"
    )
    try:
        print("== health ==")
        health = http_json("GET", "/health")
        print(f"  {health}")

        if PIN_CORE_CAPS:
            pin_core_capabilities()

        run_photo(VEHICLES_PHOTO, "vehicles")
        run_photo(OBJECTS_PHOTO, "objects")
    except SmokeFail as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS smoke_core_stack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
