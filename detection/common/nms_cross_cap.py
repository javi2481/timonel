"""NMS cross-capacidad (capa B) tras merge de caps en el bridge.

Capa A (PR2, ``class_id_for_tile_nms``): NMS **intra-capacidad** dentro del
InferenceSlicer (car vs truck, etc.).

Capa B (este módulo, ``class_id_for_cross_cap_nms``): NMS **cross-cap** por
``entity_type`` (vehicle vs face vs object…). Nunca reutilizar el mapa de A.

Tras NMS-B: dedupe espacial entre ``vehicle`` / ``object`` / ``open_vocab``
(mismo objeto emitido por COCO y YOLO-World). Preferencia:
vehicle > object > open_vocab.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import numpy as np
import supervision as sv

logger = logging.getLogger("detection.nms_cross_cap")

# IoU threshold — mismo default que supervision Detections.with_nms / slicer.
CROSS_CAP_NMS_THRESHOLD = float(os.getenv("CROSS_CAP_NMS_THRESHOLD", "0.5"))

# Modalidades de caja que compiten por el mismo objeto físico.
_SPATIAL_DEDUP_ENTITY_TYPES: frozenset[str] = frozenset(
    {"vehicle", "object", "open_vocab"}
)
# Menor = más prioritario al survivor.
_SPATIAL_DEDUP_PRIORITY: dict[str, int] = {
    "vehicle": 0,
    "object": 1,
    "open_vocab": 2,
}

# Mapa entity_type → id **solo** para NMS-B. Independiente de _TILE_CLASS_IDS.
_CROSS_CAP_CLASS_IDS: dict[str, int] = {}

# Keys que van a ``Detections.data`` (strings/objects). track_id siempre str.
_DATA_KEYS = (
    "track_id",
    "label",
    "entity_type",
    "color",
    "plate",
    "person",
    "text",
    "identity",
    "keypoints",
    "scene",
    "frame_ts",
    "vi_row",
)


def class_id_for_cross_cap_nms(entity_type: str) -> int:
    """Id estable por ``entity_type`` para NMS-B (no taxonomy COCO de tile)."""
    key = (entity_type or "vehicle").strip().lower() or "vehicle"
    if key not in _CROSS_CAP_CLASS_IDS:
        _CROSS_CAP_CLASS_IDS[key] = len(_CROSS_CAP_CLASS_IDS)
    return _CROSS_CAP_CLASS_IDS[key]


def reset_cross_cap_class_ids() -> None:
    """Solo tests: limpia el mapa dinámico."""
    _CROSS_CAP_CLASS_IDS.clear()


def _has_bbox(det: dict[str, Any]) -> bool:
    bbox = det.get("bbox")
    return isinstance(bbox, (list, tuple)) and len(bbox) >= 4


def _entity_type(det: dict[str, Any]) -> str:
    return str(det.get("entity_type") or "vehicle").strip().lower() or "vehicle"


def _bbox_xyxy(det: dict[str, Any]) -> tuple[float, float, float, float]:
    b = det["bbox"]
    return float(b[0]), float(b[1]), float(b[2]), float(b[3])


def _iou_xyxy(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return inter / union


def _safe_score(det: dict[str, Any]) -> float:
    raw = det.get("score", det.get("conf", det.get("confidence")))
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def dedupe_spatial_modality_caps(
    detections: list[dict[str, Any]],
    *,
    threshold: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Dedupe IoU entre vehicle / object / open_vocab.

    Preferencia del survivor: vehicle > object > open_vocab; empate → mayor score.
    Otras entity_types pasan intactas.
    """
    thr = CROSS_CAP_NMS_THRESHOLD if threshold is None else float(threshold)
    competing: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for det in detections:
        if _has_bbox(det) and _entity_type(det) in _SPATIAL_DEDUP_ENTITY_TYPES:
            competing.append(det)
        else:
            others.append(det)

    if len(competing) <= 1:
        return others + competing

    ordered = sorted(
        competing,
        key=lambda d: (
            _SPATIAL_DEDUP_PRIORITY.get(_entity_type(d), 99),
            -_safe_score(d),
        ),
    )
    kept: list[dict[str, Any]] = []
    suppressed = [False] * len(ordered)
    for i, det in enumerate(ordered):
        if suppressed[i]:
            continue
        kept.append(det)
        box_i = _bbox_xyxy(det)
        for j in range(i + 1, len(ordered)):
            if suppressed[j]:
                continue
            if _iou_xyxy(box_i, _bbox_xyxy(ordered[j])) >= thr:
                suppressed[j] = True
    return others + kept


def _row_to_data_fields(det: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_id": str(det.get("track_id") or ""),
        "label": det.get("label"),
        "entity_type": det.get("entity_type") or "vehicle",
        "color": det.get("color"),
        "plate": det.get("plate") if isinstance(det.get("plate"), dict) else None,
        "person": det.get("person") if isinstance(det.get("person"), dict) else None,
        "text": det.get("text"),
        "identity": det.get("identity"),
        "keypoints": det.get("keypoints")
        if isinstance(det.get("keypoints"), list)
        else None,
        "scene": det.get("scene") if isinstance(det.get("scene"), dict) else None,
        "frame_ts": det.get("frame_ts"),
        "vi_row": det,
    }


def _obj_array_1(value: Any) -> np.ndarray:
    """Array object de largo 1 que envuelve ``value`` sin aplanarlo.

    ``np.array([value], dtype=object)`` colapsa a un array N-D cuando ``value``
    es una lista rectangular (p.ej. keypoints Nx3 de pose), rompiendo luego
    ``sv.Detections.merge`` (dims distintas vs las otras caps). ``np.empty`` +
    asignación garantiza shape ``(1,)`` con el objeto intacto.
    """
    arr = np.empty(1, dtype=object)
    arr[0] = value
    return arr


def vi_det_to_detections(det: dict[str, Any]) -> sv.Detections:
    """Una detección VI con bbox → ``sv.Detections`` (len=1) para merge/NMS-B."""
    fields = _row_to_data_fields(det)
    data = {k: _obj_array_1(fields[k]) for k in _DATA_KEYS}
    return sv.Detections(
        xyxy=np.array([det["bbox"]], dtype=np.float32),
        confidence=np.array([float(det.get("score") or 0.0)], dtype=np.float32),
        class_id=np.array(
            [class_id_for_cross_cap_nms(str(fields["entity_type"]))],
            dtype=np.int32,
        ),
        data=data,
    )


def normalize_detections_data_keys(
    detections_list: list[sv.Detections],
) -> list[sv.Detections]:
    """Rellena keys faltantes en ``data`` para que ``Detections.merge`` no falle."""
    if not detections_list:
        return []
    all_keys: set[str] = set()
    for det in detections_list:
        if det.data:
            all_keys.update(det.data.keys())
    if not all_keys:
        return detections_list

    out: list[sv.Detections] = []
    for det in detections_list:
        if det.is_empty():
            continue
        n = len(det)
        data = dict(det.data) if det.data else {}
        for key in all_keys:
            if key not in data:
                data[key] = np.array([None] * n, dtype=object)
        out.append(
            sv.Detections(
                xyxy=det.xyxy,
                mask=det.mask,
                confidence=det.confidence,
                class_id=det.class_id,
                tracker_id=det.tracker_id,
                data=data,
            )
        )
    return out


def detections_to_vi_dets(detections: sv.Detections) -> list[dict[str, Any]]:
    """Survivors post-NMS → dicts VI (extras del survivor vía ``vi_row``)."""
    out: list[dict[str, Any]] = []
    n = len(detections)
    rows = detections.data.get("vi_row") if detections.data else None
    for i in range(n):
        if rows is not None and rows[i] is not None:
            row = dict(rows[i])
        else:
            row = {
                "bbox": [float(x) for x in detections.xyxy[i]],
                "score": float(detections.confidence[i])
                if detections.confidence is not None
                else 0.0,
            }
            if detections.data:
                for key in _DATA_KEYS:
                    if key == "vi_row":
                        continue
                    vals = detections.data.get(key)
                    if vals is not None:
                        row[key] = vals[i]
        # track_id string en data / dict (nunca tracker_id numérico).
        if detections.data and detections.data.get("track_id") is not None:
            tid = detections.data["track_id"][i]
            if tid is not None and str(tid) != "":
                row["track_id"] = str(tid)
        out.append(row)
    return out


def apply_cross_cap_nms(
    detections: list[dict[str, Any]],
    *,
    threshold: Optional[float] = None,
) -> list[dict[str, Any]]:
    """NMS-B por entity_type + dedupe espacial vehicle/object/open_vocab.

    Survivor NMS-B = mayor score (``with_nms``). Extras (track_id, plate, …)
    solo del survivor. Luego preferencia vehicle > object > open_vocab.
    """
    thr = CROSS_CAP_NMS_THRESHOLD if threshold is None else float(threshold)
    with_bbox: list[dict[str, Any]] = []
    without_bbox: list[dict[str, Any]] = []
    for det in detections:
        if _has_bbox(det):
            with_bbox.append(det)
        else:
            without_bbox.append(det)

    if len(with_bbox) <= 1:
        return without_bbox + with_bbox

    pieces = [vi_det_to_detections(d) for d in with_bbox]
    pieces = normalize_detections_data_keys(pieces)
    merged = sv.Detections.merge(pieces)
    # Nunca IOS — overlap_metric=IOU explícito (default supervision, pinneado).
    kept = merged.with_nms(
        threshold=thr,
        class_agnostic=False,
        overlap_metric=sv.OverlapMetric.IOU,
    )
    survivors = detections_to_vi_dets(kept)
    survivors = dedupe_spatial_modality_caps(survivors, threshold=thr)
    return without_bbox + survivors
