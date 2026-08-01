"""Señales de tránsito vía YOLO-World (open-vocab :8093).

Producto: ``entity_type:"sign"`` + tracks ``s-*``; label colapsado a ``"sign"``.
``categoryName`` + score del prompt van como hint (metadata), no como label.

Backend default: ``PADDLEX_SIGNS_OV_URL`` → ``paddlex-open-vocab:8093``.
Rollback COCO legacy: ``SIGNS_BACKEND=coco`` + profile ``legacy-signs`` (:8088).
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from detection.common.paddlex_client import build_open_vocab_body
from detection.common.tracking import IoUTracker

logger = logging.getLogger("detection.signs")

# Producto (YOLO-World). Medición A/B propone defaults; confirmar con gate humano.
PADDLEX_SIGNS_OV_URL = os.getenv(
    "PADDLEX_SIGNS_OV_URL", "http://paddlex-open-vocab:8093"
)
PADDLEX_SIGNS_OV_PREDICT_PATH = os.getenv(
    "PADDLEX_SIGNS_OV_PREDICT_PATH", "/open-vocabulary-detection"
)
# Propuesto por measure_signs_ov_ab.py (fo_signs n=2, seed=51): OV-B @0.05
# → P=0.667 R=0.500 @960 (== hires). Gate humano confirma antes de fijar producto.
SIGNS_OV_PROMPT = os.getenv(
    "SIGNS_OV_PROMPT", "traffic sign,stop sign,traffic light"
)
# Perilla propia (no hereda SIGNS_THRESHOLD / escala COCO).
SIGNS_OV_THRESHOLD = float(os.getenv("SIGNS_OV_THRESHOLD", "0.05"))

# Legacy COCO (:8088) — solo rollback / profile legacy-signs.
PADDLEX_SIGNS_URL = os.getenv("PADDLEX_SIGNS_URL", "http://paddlex-signs:8088")
PADDLEX_SIGNS_PREDICT_PATH = os.getenv(
    "PADDLEX_SIGNS_PREDICT_PATH", "/object-detection"
)
SIGNS_THRESHOLD = float(os.getenv("SIGNS_THRESHOLD", "0.1"))

# ov (default) | coco (rollback nombrado)
SIGNS_BACKEND = os.getenv("SIGNS_BACKEND", "ov").strip().lower()

ENABLE_SIGNS = os.getenv("ENABLE_SIGNS", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
IOU_THRESHOLD = float(os.getenv("TRACK_IOU_THRESHOLD", "0.3"))

# COCO + nombres típicos de fine-tune (solo SIGNS_BACKEND=coco)
DEFAULT_SIGN_LABELS = {
    "traffic light",
    "stop sign",
    "parking meter",
    "fire hydrant",
    "traffic_sign",
    "traffic sign",
    "sign",
    "speed_limit",
    "yield",
    "crosswalk_sign",
}

_raw = os.getenv("SIGNS_LABELS", "")
SIGN_LABELS = (
    {s.strip().lower() for s in _raw.split(",") if s.strip()}
    if _raw.strip()
    else DEFAULT_SIGN_LABELS
)

_signs_tracker = IoUTracker(IOU_THRESHOLD)


def reset_signs_tracker() -> None:
    global _signs_tracker
    _signs_tracker = IoUTracker(IOU_THRESHOLD)


def normalize_signs_result(
    data: dict[str, Any], *, backend: Optional[str] = None
) -> list[dict[str, Any]]:
    """Traduce respuesta PaddleX → dets ``sign`` / ``s-*``.

    Path OV: label siempre ``"sign"``; ``categoryName``+score como hint.
    Path coco (legacy): filtra ``SIGN_LABELS`` y conserva el label COCO.
    ``backend`` opcional para tests / harness (default: ``SIGNS_BACKEND``).
    """
    result = data.get("result", data)
    boxes: list[dict[str, Any]] = []
    if isinstance(result, dict):
        # Serving 3.7: detectedObjects[{bbox,categoryName,score}].
        raw = result.get("detectedObjects") or result.get("boxes") or []
        if isinstance(raw, list):
            boxes = raw
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                boxes.extend(
                    item.get("detectedObjects") or item.get("boxes") or []
                )

    use_ov = (backend or SIGNS_BACKEND) != "coco"
    coords: list[list[float]] = []
    meta: list[dict[str, Any]] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        category = str(
            box.get("categoryName") or box.get("label") or box.get("cls_name") or ""
        ).strip()
        category_l = category.lower()
        if not use_ov and SIGN_LABELS and category_l not in SIGN_LABELS:
            continue
        coord = box.get("coordinate") or box.get("bbox")
        if not coord or len(coord) < 4:
            continue
        bbox = [float(coord[0]), float(coord[1]), float(coord[2]), float(coord[3])]
        score = float(box.get("score") or box.get("det_score") or 0.0)
        if use_ov:
            meta.append(
                {
                    "label": "sign",
                    "score": score,
                    "bbox": bbox,
                    "hint": category or "sign",
                }
            )
        else:
            meta.append(
                {
                    "label": category_l or "sign",
                    "score": score,
                    "bbox": bbox,
                }
            )
        coords.append(bbox)

    track_ids = _signs_tracker.assign(coords)
    now = datetime.now(timezone.utc).isoformat()
    out: list[dict[str, Any]] = []
    for tid, m in zip(track_ids, meta):
        det: dict[str, Any] = {
            "track_id": f"s-{tid}",
            "label": m["label"],
            "score": m["score"],
            "bbox": m["bbox"],
            "entity_type": "sign",
            "frame_ts": now,
        }
        if "hint" in m:
            # Pista del prompt OV (categoryName); no es label autoritativo.
            det["hint"] = m["hint"]
        out.append(det)
    return out


async def infer_signs(
    client: httpx.AsyncClient, jpeg: bytes
) -> Optional[list[dict[str, Any]]]:
    """POST JPEG al backend signs (OV por default). None ante fallo."""
    if not ENABLE_SIGNS:
        return None

    if SIGNS_BACKEND == "coco":
        url = f"{PADDLEX_SIGNS_URL.rstrip('/')}{PADDLEX_SIGNS_PREDICT_PATH}"
        body: dict[str, Any] = {
            "image": base64.b64encode(jpeg).decode("ascii"),
            "threshold": SIGNS_THRESHOLD,
        }
    else:
        url = f"{PADDLEX_SIGNS_OV_URL.rstrip('/')}{PADDLEX_SIGNS_OV_PREDICT_PATH}"
        body = build_open_vocab_body(
            jpeg, prompt=SIGNS_OV_PROMPT, threshold=SIGNS_OV_THRESHOLD
        )

    try:
        resp = await client.post(url, json=body, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Signs infer error (isolated): %s", exc)
        return None

    if not isinstance(data, dict):
        return []
    if data.get("errorCode") not in (None, 0, "0"):
        logger.debug("Signs error: %s", data.get("errorMsg"))
        return None
    return normalize_signs_result(data)
