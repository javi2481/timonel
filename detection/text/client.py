"""OCR de escena / carteles (reusa paddlex-ocr :8081).

Opcional (ENABLE_SCENE_OCR). Distinto de plates/: no filtra solo patentes;
devuelve líneas de texto con score. Caída aislada.

Además del frame completo, puede OCR-ear crops de dets ``sign``
(``SCENE_OCR_FROM_SIGNS``) — mismo patrón que plates sobre vehículos.
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import httpx

from detection.plates.client import crop_bbox

logger = logging.getLogger("detection.text")

PADDLEX_OCR_URL = os.getenv("PADDLEX_OCR_URL", "http://paddlex-ocr:8081")
ENABLE_SCENE_OCR = os.getenv("ENABLE_SCENE_OCR", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
SCENE_OCR_MIN_SCORE = float(os.getenv("SCENE_OCR_MIN_SCORE", "0.3"))
SCENE_OCR_MAX_LINES = max(1, int(os.getenv("SCENE_OCR_MAX_LINES", "20")))
OCR_HTTP_TIMEOUT = float(os.getenv("OCR_HTTP_TIMEOUT", "5"))

# Enrich post-signs: crop carteles detectados → OCR (coords → espacio hires).
SCENE_OCR_FROM_SIGNS = os.getenv(
    "SCENE_OCR_FROM_SIGNS", "true"
).strip().lower() in ("1", "true", "yes")
SCENE_OCR_SIGN_TOPK = max(1, int(os.getenv("SCENE_OCR_SIGN_TOPK", "3")))
# Bajo a propósito: carteles publicitarios a menudo tienen score OV débil (~0.1–0.2).
SCENE_OCR_SIGN_MIN_SCORE = float(os.getenv("SCENE_OCR_SIGN_MIN_SCORE", "0.1"))


def _offset_geom(
    bbox: Optional[list[float]],
    polygon: Optional[list[list[float]]],
    ox: float,
    oy: float,
) -> tuple[Optional[list[float]], Optional[list[list[float]]]]:
    """Trasladar bbox/poly del espacio crop → frame hires."""
    out_bbox = None
    if bbox is not None and len(bbox) >= 4:
        out_bbox = [
            float(bbox[0]) + ox,
            float(bbox[1]) + oy,
            float(bbox[2]) + ox,
            float(bbox[3]) + oy,
        ]
    out_poly = None
    if polygon:
        try:
            out_poly = [[float(p[0]) + ox, float(p[1]) + oy] for p in polygon]
        except (TypeError, ValueError, IndexError):
            out_poly = None
    return out_bbox, out_poly


def normalize_scene_ocr_result(
    data: dict[str, Any],
    *,
    offset_xy: tuple[float, float] = (0.0, 0.0),
) -> list[dict[str, Any]]:
    """Traduce respuesta OCR general → dets entity_type=text.

    ``offset_xy`` suma (ox, oy) a bbox/polygon cuando el JPEG era un crop.
    """
    result = data.get("result", data) if isinstance(data, dict) else {}
    if not isinstance(result, dict):
        return []

    ox, oy = float(offset_xy[0]), float(offset_xy[1])

    # (text, score, bbox_xyxy|None, polygon [[x,y],…]|None)
    lines: list[
        tuple[str, float, Optional[list[float]], Optional[list[list[float]]]]
    ] = []

    ocr_results = result.get("ocrResults") or []
    if isinstance(ocr_results, list) and ocr_results:
        first = ocr_results[0] if isinstance(ocr_results[0], dict) else {}
        pruned = first.get("prunedResult") if isinstance(first, dict) else {}
        if isinstance(pruned, dict):
            texts = pruned.get("rec_texts") or []
            scores = pruned.get("rec_scores") or []
            polys = pruned.get("dt_polys") or pruned.get("rec_polys") or []
            for i, text in enumerate(texts):
                score = float(scores[i]) if i < len(scores) else 0.0
                bbox = None
                polygon: Optional[list[list[float]]] = None
                if i < len(polys) and isinstance(polys[i], (list, tuple)):
                    pts = polys[i]
                    try:
                        polygon = [[float(p[0]), float(p[1])] for p in pts]
                        xs = [p[0] for p in polygon]
                        ys = [p[1] for p in polygon]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]
                    except (TypeError, ValueError, IndexError):
                        bbox = None
                        polygon = None
                if ox or oy:
                    bbox, polygon = _offset_geom(bbox, polygon, ox, oy)
                lines.append((str(text), score, bbox, polygon))

    # shape alternativo: texts / scores en raíz
    if not lines:
        texts = result.get("rec_texts") or result.get("texts") or []
        scores = result.get("rec_scores") or result.get("scores") or []
        for i, text in enumerate(texts):
            score = float(scores[i]) if i < len(scores) else 0.0
            lines.append((str(text), score, None, None))

    lines = sorted(lines, key=lambda t: t[1], reverse=True)
    lines = [
        (t, s, b, poly)
        for t, s, b, poly in lines
        if s >= SCENE_OCR_MIN_SCORE and str(t).strip()
    ][:SCENE_OCR_MAX_LINES]

    now = datetime.now(timezone.utc).isoformat()
    dets: list[dict[str, Any]] = []
    for i, (text, score, bbox, polygon) in enumerate(lines):
        det: dict[str, Any] = {
            "track_id": f"t-{i}",
            "label": "text",
            "score": score,
            "bbox": bbox or [0.0, 0.0, 1.0, 1.0],
            "entity_type": "text",
            "text": text.strip(),
            "frame_ts": now,
        }
        if polygon and len(polygon) >= 3:
            det["polygon"] = polygon
        dets.append(det)
    return dets


def _renumber_text_tracks(detections: list[dict[str, Any]]) -> None:
    """Reasigna track_id t-* a todos los dets text (in-place)."""
    texts = [d for d in detections if d.get("entity_type") == "text"]
    texts.sort(key=lambda d: float(d.get("score") or 0.0), reverse=True)
    # Cap global tras merge full-frame + crops.
    keep = set(id(d) for d in texts[:SCENE_OCR_MAX_LINES])
    drop = [d for d in texts if id(d) not in keep]
    for d in drop:
        detections.remove(d)
    texts = [d for d in detections if d.get("entity_type") == "text"]
    texts.sort(key=lambda d: float(d.get("score") or 0.0), reverse=True)
    for i, d in enumerate(texts):
        d["track_id"] = f"t-{i}"


async def infer_scene_ocr(
    client: httpx.AsyncClient, jpeg: bytes
) -> Optional[list[dict[str, Any]]]:
    """POST frame completo a /ocr. None ante fallo."""
    if not ENABLE_SCENE_OCR:
        return None
    url = f"{PADDLEX_OCR_URL.rstrip('/')}/ocr"
    b64 = base64.b64encode(jpeg).decode("ascii")
    try:
        resp = await client.post(
            url,
            json={"file": b64, "fileType": 1},
            timeout=OCR_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Scene OCR infer error (isolated): %s", exc)
        return None

    if not isinstance(data, dict):
        return []
    return normalize_scene_ocr_result(data)


async def _ocr_crop_to_text_dets(
    client: httpx.AsyncClient,
    crop_jpeg: bytes,
    *,
    offset_xy: tuple[float, float],
) -> list[dict[str, Any]]:
    """POST crop → líneas text con coords en hires. [] ante fallo."""
    url = f"{PADDLEX_OCR_URL.rstrip('/')}/ocr"
    b64 = base64.b64encode(crop_jpeg).decode("ascii")
    try:
        resp = await client.post(
            url,
            json={"file": b64, "fileType": 1},
            timeout=OCR_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Sign-crop OCR error (isolated): %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    return normalize_scene_ocr_result(data, offset_xy=offset_xy)


async def enrich_text_from_sign_crops(
    client: httpx.AsyncClient,
    frame_hires,
    detections: list[dict[str, Any]],
    encode_jpeg_fn: Callable[..., Optional[bytes]],
) -> None:
    """Si SCENE_OCR_FROM_SIGNS, OCR top-K crops de ``sign`` y agrega dets text.

    Mutates ``detections`` in-place. Caída aislada (no degrada el bridge).
    """
    if not ENABLE_SCENE_OCR or not SCENE_OCR_FROM_SIGNS or not detections:
        return

    eligible = sorted(
        (
            d
            for d in detections
            if d.get("entity_type") == "sign"
            and float(d.get("score") or 0.0) >= SCENE_OCR_SIGN_MIN_SCORE
            and isinstance(d.get("bbox"), (list, tuple))
            and len(d["bbox"]) >= 4
        ),
        key=lambda d: float(d.get("score") or 0.0),
        reverse=True,
    )[:SCENE_OCR_SIGN_TOPK]

    if not eligible:
        return

    added: list[dict[str, Any]] = []
    for sign in eligible:
        bbox = [float(x) for x in sign["bbox"][:4]]
        crop = crop_bbox(frame_hires, bbox)
        if crop is None:
            continue
        crop_jpeg = encode_jpeg_fn(crop)
        if crop_jpeg is None:
            continue
        ox, oy = bbox[0], bbox[1]
        lines = await _ocr_crop_to_text_dets(
            client, crop_jpeg, offset_xy=(ox, oy)
        )
        for det in lines:
            det["source"] = "sign_crop"
            if sign.get("track_id"):
                det["sign_track_id"] = sign["track_id"]
            added.append(det)

    if not added:
        return

    detections.extend(added)
    _renumber_text_tracks(detections)
