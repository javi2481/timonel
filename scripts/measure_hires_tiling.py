#!/usr/bin/env python3
"""Hires multi-tile measure (vehicles Core) — pad to width=1920, not upscale.

Native Core pack is ≤640 (single tile). Padding onto a 1920-wide canvas creates
multiple InferenceSlicer tiles while keeping native pixels (GT bboxes unchanged
when content is placed at top-left).

Compares bridge-preprocess single JPEG @1920 vs infer_vehicles_tiled_sync.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import cv2
import httpx
import numpy as np

_REPO = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(_REPO))

from detection.common.geometry import encode_jpeg, maybe_resize_for_infer
from detection.common.paddlex_client import post_image_predict_sync
from detection.vehicles.client import infer_vehicles_tiled_sync, normalize_vehicle_result

OUT = Path(os.getenv("EVAL_OUT", "imagenes_muestra"))
TARGET_W = int(os.getenv("HIRES_TARGET_WIDTH", "1920"))
SLICE = int(os.getenv("INFER_SLICE_WH", "640"))
OVERLAP = int(os.getenv("INFER_OVERLAP_WH", "100"))
PADDLEX_URL = os.getenv("PADDLEX_URL", "http://127.0.0.1:8080")
REPORT = Path(os.getenv("REPORT", "scripts/eval_report_hires_tiling.json"))
PAUSE_S = float(os.getenv("HIRES_PAUSE_S", "0.5"))
MAX_FIXTURES = int(os.getenv("HIRES_MAX_FIXTURES", "0"))  # 0 = all

logging.basicConfig(level=logging.WARNING)


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def match_tp(gts: list[list[float]], preds: list[list[float]], thr: float = 0.5) -> int:
    used: set[int] = set()
    tp = 0
    for g in gts:
        best, bj = -1.0, -1
        for j, p in enumerate(preds):
            if j in used:
                continue
            s = iou(g, p)
            if s > best:
                best, bj = s, j
        if best >= thr and bj >= 0:
            used.add(bj)
            tp += 1
    return tp


def n_tiles(w: int, h: int, sw: int = SLICE, ow: int = OVERLAP) -> int:
    step = max(1, sw - ow)

    def axes(length: int) -> list[int]:
        xs = list(range(0, max(1, length - sw + 1), step))
        last = max(0, length - sw)
        if not xs or xs[-1] != last:
            xs.append(last)
        return sorted(set(xs))

    return len(axes(w)) * len(axes(h))


def pad_hires(frame: np.ndarray) -> np.ndarray:
    """Place native frame at top-left of a TARGET_W-wide canvas (black fill)."""
    h, w = frame.shape[:2]
    nh = max(h, int(round(h * TARGET_W / float(w))))
    canvas = np.zeros((nh, TARGET_W, 3), dtype=frame.dtype)
    canvas[:h, :w] = frame
    return canvas


def preds_bridge(frame: np.ndarray) -> list[dict]:
    frame_infer, _, _ = maybe_resize_for_infer(frame)
    jpeg = encode_jpeg(frame_infer)
    if jpeg is None:
        return []
    with httpx.Client(timeout=90.0) as client:
        data = post_image_predict_sync(
            client,
            base_url=PADDLEX_URL,
            predict_path="/vehicle-attribute-recognition",
            jpeg=jpeg,
            timeout=90.0,
            label="hires-pad-bridge",
            warn_on_error=True,
        )
    return normalize_vehicle_result(data) if data else []


def main() -> int:
    os.environ.setdefault("BRIDGE_MAX_WIDTH", str(TARGET_W))
    gt = json.loads((OUT / "gt" / "vehicles.json").read_text(encoding="utf-8"))
    fixtures = gt.get("fixtures") or []
    if MAX_FIXTURES > 0:
        fixtures = fixtures[:MAX_FIXTURES]

    tp_b = gt_n = tp_t = 0
    lat_b: list[float] = []
    lat_t: list[float] = []
    tiles: list[int] = []
    fails = 0

    for fx in fixtures:
        path = OUT / fx["file"]
        if not path.exists():
            print("SKIP", fx["file"])
            continue
        arr = np.frombuffer(path.read_bytes(), dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            print("SKIP decode", path.name)
            continue
        hires = pad_hires(frame)
        gts = [[float(x) for x in b] for b in (fx.get("bboxes") or [])]
        nt = n_tiles(hires.shape[1], hires.shape[0])
        tiles.append(nt)

        t0 = time.perf_counter()
        pb = preds_bridge(hires)
        lat_b.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        pt = infer_vehicles_tiled_sync(hires) or []
        lat_t.append(time.perf_counter() - t0)

        if not pb and not pt:
            fails += 1

        bb = [d["bbox"] for d in pb if d.get("bbox")]
        tb = [d["bbox"] for d in pt if d.get("bbox")]
        tpb = match_tp(gts, bb)
        tpt = match_tp(gts, tb)
        tp_b += tpb
        tp_t += tpt
        gt_n += len(gts)
        print(
            f"{path.name}: tiles={nt} bridge={tpb}/{len(gts)} "
            f"tiled={tpt}/{len(gts)} "
            f"lat_b={lat_b[-1]:.2f}s lat_t={lat_t[-1]:.2f}s "
            f"pred_b={len(bb)} pred_t={len(tb)}"
        )
        time.sleep(PAUSE_S)

    def rate(tp: int, n: int) -> float:
        return round(tp / n, 4) if n else 0.0

    b_rate = rate(tp_b, gt_n)
    t_rate = rate(tp_t, gt_n)
    # Match-only hint; ops decision also weighs latency (see docs/archive/tiling-nms/hires-tiling-measure.md).
    if t_rate > b_rate:
        decision = (
            f"match_up (+{round(t_rate - b_rate, 4)}); "
            "KEEP ENABLE_INFER_TILING=false until latency acceptable / native hires pack"
        )
    else:
        decision = "KEEP ENABLE_INFER_TILING=false"
    report = {
        "date": time.strftime("%Y-%m-%d"),
        "method": (
            "pad Core vehicles onto width=1920 canvas "
            "(native pixels top-left; black fill). Not bilinear upscale."
        ),
        "target_width": TARGET_W,
        "slice_wh": SLICE,
        "overlap_wh": OVERLAP,
        "n_fixtures": len(lat_b),
        "n_multi_tile_frames": sum(1 for t in tiles if t > 1),
        "tiles_per_frame": tiles,
        "empty_both_paths": fails,
        "bridge_preprocess_1920_pad": {
            "bbox_match_rate": b_rate,
            "tp": tp_b,
            "gt": gt_n,
            "mean_latency_s": round(sum(lat_b) / len(lat_b), 3) if lat_b else None,
        },
        "tiled_sync_hires_pad": {
            "bbox_match_rate": t_rate,
            "tp": tp_t,
            "gt": gt_n,
            "mean_latency_s": round(sum(lat_t) / len(lat_t), 3) if lat_t else None,
        },
        "pr2_baseline_native_pack": {
            "direct": 0.4691,
            "bridge_preprocess": 0.358,
            "tiled_sync": 0.358,
            "note": "native ≤640 → mostly single tile",
        },
        "decision": decision,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
