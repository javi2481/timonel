"""Scaffold open-vocabulary detection (experimental). GATE: ver README."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from detection.common.paddlex_client import build_open_vocab_body
from detection.common.tracking import IoUTracker

logger = logging.getLogger("detection.open_vocab")

PADDLEX_OPEN_VOCAB_URL = os.getenv(
    "PADDLEX_OPEN_VOCAB_URL", "http://paddlex-open-vocab:8093"
)
ENABLE_OPEN_VOCAB = os.getenv("ENABLE_OPEN_VOCAB", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)
# Cola larga fuera del piso COCO. Ownership: "señal" es de signs — no incluir
# "traffic sign" / "stop sign" / "traffic light" (evita duplicar sign/s-* y ov-*).
_DEFAULT_OPEN_VOCAB_PROMPT = (
    "helmet,hard hat,safety vest,reflective vest,fire extinguisher,forklift,"
    "traffic cone,barricade,wheelchair,stroller,crutches,ladder,scaffold,"
    "generator,pallet,shopping cart,scooter,warning triangle,bollard,"
    "stapler,wrench,hammer,drill,toolbox,backpack,suitcase,umbrella"
)
OPEN_VOCAB_PROMPT = os.getenv("OPEN_VOCAB_PROMPT", _DEFAULT_OPEN_VOCAB_PROMPT)
# PaddleX pipeline guarda thresholds en self pero no los aplica si el request
# no manda override (bug upstream). El client siempre envía el dict.
OPEN_VOCAB_THRESHOLD = float(os.getenv("OPEN_VOCAB_THRESHOLD", "0.05"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30.0"))
_tracker = IoUTracker(0.3)


def normalize_open_vocab_result(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = data.get("result", data)
    # Serving 3.7 YOLO-World → detectedObjects[{bbox,categoryName,score}];
    # create_model / older shape → boxes[{coordinate|bbox,label,score}].
    boxes: list[Any] = []
    if isinstance(result, dict):
        raw = result.get("detectedObjects") or result.get("boxes") or []
        if isinstance(raw, list):
            boxes = raw
    coords, meta = [], []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        coord = box.get("coordinate") or box.get("bbox")
        if not coord or len(coord) < 4:
            continue
        bbox = [float(c) for c in coord[:4]]
        coords.append(bbox)
        meta.append(
            {
                "label": str(
                    box.get("categoryName") or box.get("label") or "open"
                ),
                "score": float(box.get("score") or 0.0),
                "bbox": bbox,
            }
        )
    tids = _tracker.assign(coords)
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "track_id": f"ov-{tid}",
            "label": m["label"],
            "score": m["score"],
            "bbox": m["bbox"],
            "entity_type": "open_vocab",
            "frame_ts": now,
        }
        for tid, m in zip(tids, meta)
    ]


async def infer_open_vocab(
    client: httpx.AsyncClient,
    jpeg: bytes,
    *,
    prompt: Optional[str] = None,
) -> Optional[list[dict[str, Any]]]:
    if not ENABLE_OPEN_VOCAB:
        return None
    use_prompt = (prompt or "").strip() or OPEN_VOCAB_PROMPT
    url = f"{PADDLEX_OPEN_VOCAB_URL.rstrip('/')}/open-vocabulary-detection"
    try:
        resp = await client.post(
            url,
            json=build_open_vocab_body(
                jpeg, prompt=use_prompt, threshold=OPEN_VOCAB_THRESHOLD
            ),
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("Open-vocab error (isolated): %s", exc)
        return None
    if not isinstance(data, dict) or data.get("errorCode") not in (None, 0, "0"):
        return None
    return normalize_open_vocab_result(data)
