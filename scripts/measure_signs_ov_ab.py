#!/usr/bin/env python3
"""Fase 0 — A/B signs: COCO :8088 vs YOLO-World :8093 (prompt/threshold/resolución).

Usa ``build_open_vocab_body`` (misma forma que producción). Reporta fo_signs
(P/R con GT) y AR cualitativo en secciones SEPARADAS — no promediar.

Uso (host, servicios up):
  python scripts/measure_signs_ov_ab.py
  python scripts/measure_signs_ov_ab.py --signs-url http://127.0.0.1:8088 --ov-url http://127.0.0.1:8093

Brazos:
  Baseline@960 COCO thr=0.1
  OV-A prompt="traffic sign" @ thr 0.05/0.1/0.2 × 960/hires
  OV-B prompt="traffic sign,stop sign,traffic light" @ mismos thr × 960/hires
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detection.common.geometry import encode_jpeg, maybe_resize_for_infer  # noqa: E402
from detection.common.paddlex_client import build_open_vocab_body  # noqa: E402

try:
    import cv2  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise SystemExit("opencv-python requerido") from exc

# Brazo "producción histórica / plan": 960 px de ancho (BRIDGE_MAX_WIDTH medido).
PROD_MAX_WIDTH = 960

OV_A_PROMPT = "traffic sign"
OV_B_PROMPT = "traffic sign,stop sign,traffic light"
THRESHOLDS = (0.05, 0.1, 0.2)

# Fotos señalética AR (si existen). No inventar fixtures.
AR_GLOBS = (
    "ar_sign*",
    "ar_senal*",
    "senal_ar*",
    "señal_ar*",
    "*argentina*sign*",
)


def _iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
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


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {raw[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"URL error: {exc}") from exc


def _extract_boxes(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = data.get("result", data)
    boxes: list[Any] = []
    if isinstance(result, dict):
        raw = result.get("detectedObjects") or result.get("boxes") or []
        if isinstance(raw, list):
            boxes = raw
    out: list[dict[str, Any]] = []
    for box in boxes:
        if not isinstance(box, dict):
            continue
        coord = box.get("coordinate") or box.get("bbox")
        if not coord or len(coord) < 4:
            continue
        label = str(
            box.get("categoryName") or box.get("label") or box.get("cls_name") or ""
        )
        score = float(box.get("score") or box.get("det_score") or 0.0)
        out.append(
            {
                "bbox": [float(c) for c in coord[:4]],
                "label": label,
                "score": score,
            }
        )
    return out


def _match_pr(
    preds: list[dict[str, Any]],
    gts: list[list[float]],
    iou_thr: float = 0.5,
) -> tuple[int, int, int, float, float]:
    """Informal P/R: greedy IoU match. Returns tp, fp, fn, precision, recall."""
    matched_gt: set[int] = set()
    tp = 0
    for p in sorted(preds, key=lambda d: d["score"], reverse=True):
        best_i, best_iou = -1, 0.0
        for i, g in enumerate(gts):
            if i in matched_gt:
                continue
            v = _iou(p["bbox"], g)
            if v > best_iou:
                best_iou, best_i = v, i
        if best_i >= 0 and best_iou >= iou_thr:
            matched_gt.add(best_i)
            tp += 1
    fp = len(preds) - tp
    fn = len(gts) - tp
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return tp, fp, fn, prec, rec


def _jpeg_at_width(path: Path, max_width: Optional[int]) -> tuple[bytes, int, int]:
    """Encode JPEG; si max_width, replica maybe_resize_for_infer con ese techo."""
    frame = cv2.imread(str(path))
    if frame is None:
        raise RuntimeError(f"no se pudo leer {path}")
    h0, w0 = frame.shape[:2]
    if max_width is None:
        jpeg = encode_jpeg(frame)
        if jpeg is None:
            raise RuntimeError(f"encode falló {path}")
        return jpeg, w0, h0
    # Temporarily honor plan arm width without mutating process BRIDGE_MAX_WIDTH.
    import detection.common.geometry as geom

    prev = geom.BRIDGE_MAX_WIDTH
    geom.BRIDGE_MAX_WIDTH = int(max_width)
    try:
        frame_infer, _, _ = maybe_resize_for_infer(frame)
    finally:
        geom.BRIDGE_MAX_WIDTH = prev
    jpeg = encode_jpeg(frame_infer)
    if jpeg is None:
        raise RuntimeError(f"encode falló {path}")
    hi, wi = frame_infer.shape[:2]
    return jpeg, wi, hi


def _predict_coco(
    url: str, jpeg: bytes, threshold: float, timeout: float
) -> list[dict[str, Any]]:
    b64 = base64.b64encode(jpeg).decode("ascii")
    data = _post_json(
        f"{url.rstrip('/')}/object-detection",
        {"image": b64, "threshold": threshold},
        timeout,
    )
    if data.get("errorCode") not in (None, 0, "0"):
        raise RuntimeError(f"COCO error: {data.get('errorMsg')}")
    # Filtrar labels de señal como el client legacy.
    sign_labels = {
        "traffic light",
        "stop sign",
        "parking meter",
        "fire hydrant",
        "traffic_sign",
        "traffic sign",
        "sign",
    }
    return [
        b
        for b in _extract_boxes(data)
        if b["label"].strip().lower() in sign_labels
    ]


def _predict_ov(
    url: str, jpeg: bytes, prompt: str, threshold: float, timeout: float
) -> list[dict[str, Any]]:
    # Paridad producción: builder compartido.
    body = build_open_vocab_body(jpeg, prompt=prompt, threshold=threshold)
    data = _post_json(
        f"{url.rstrip('/')}/open-vocabulary-detection", body, timeout
    )
    if data.get("errorCode") not in (None, 0, "0"):
        raise RuntimeError(f"OV error: {data.get('errorMsg')}")
    return _extract_boxes(data)


def _load_fo_signs(out: Path) -> list[dict[str, Any]]:
    gt_path = out / "gt" / "signs.json"
    if not gt_path.is_file():
        return []
    payload = json.loads(gt_path.read_text(encoding="utf-8"))
    fixtures = payload.get("fixtures") or []
    rows: list[dict[str, Any]] = []
    for fx in fixtures:
        fpath = out / fx["file"]
        if not fpath.is_file():
            alt = out / fx.get("pack_file", "")
            fpath = alt if alt.is_file() else fpath
        if not fpath.is_file():
            print(f"WARN: falta imagen {fx.get('file')}", file=sys.stderr)
            continue
        rows.append(
            {
                "id": fx["id"],
                "path": fpath,
                "bboxes": fx.get("bboxes") or [],
                "labels": fx.get("labels") or [],
            }
        )
    return rows


def _find_ar_photos(out: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in AR_GLOBS:
        found.extend(sorted(out.glob(pattern)))
    # Dedup
    uniq: list[Path] = []
    seen: set[Path] = set()
    for p in found:
        rp = p.resolve()
        if rp not in seen and p.is_file():
            seen.add(rp)
            uniq.append(p)
    return uniq


def _health(url: str, timeout: float = 3.0) -> bool:
    for suffix in ("/docs", "/openapi.json", "/"):
        try:
            with urlopen(f"{url.rstrip('/')}{suffix}", timeout=timeout) as resp:
                if 200 <= int(getattr(resp, "status", 200) or 200) < 500:
                    return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "imagenes_muestra")
    ap.add_argument("--signs-url", default="http://127.0.0.1:8088")
    ap.add_argument("--ov-url", default="http://127.0.0.1:8093")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument(
        "--report",
        type=Path,
        default=ROOT / "scripts" / "measure_signs_ov_ab_report.json",
    )
    args = ap.parse_args()

    print("== health ==")
    signs_ok = _health(args.signs_url)
    ov_ok = _health(args.ov_url)
    print(f"  paddlex-signs {args.signs_url}: {'OK' if signs_ok else 'DOWN'}")
    print(f"  paddlex-open-vocab {args.ov_url}: {'OK' if ov_ok else 'DOWN'}")
    if not ov_ok:
        print(
            "BLOCKER: :8093 no healthy. Se shippea builder+script; "
            "defaults producto quedan pending.",
            file=sys.stderr,
        )
        # Aún así intentamos si signs está; OV es crítico.
    if not signs_ok:
        print(
            "WARN: :8088 down — brazo Baseline COCO se omite.",
            file=sys.stderr,
        )

    fo = _load_fo_signs(args.out)
    ar = _find_ar_photos(args.out)
    print(f"\n== fixtures ==")
    print(f"  fo_signs (GT): {len(fo)}")
    print(f"  AR cualitativo: {len(ar)}")
    if not ar:
        print(
            "  AR arm PENDING — no hay fotos de señalética AR en imagenes_muestra/ "
            f"(globs: {', '.join(AR_GLOBS)}). No se inventan fixtures."
        )

    arms: list[dict[str, Any]] = []
    # Baseline COCO @960
    if signs_ok:
        arms.append(
            {
                "name": "Baseline@960",
                "kind": "coco",
                "prompt": None,
                "threshold": 0.1,
                "max_width": PROD_MAX_WIDTH,
            }
        )
    if ov_ok:
        for prompt, tag in ((OV_A_PROMPT, "OV-A"), (OV_B_PROMPT, "OV-B")):
            for thr in THRESHOLDS:
                for res_name, mw in (("960", PROD_MAX_WIDTH), ("hires", None)):
                    arms.append(
                        {
                            "name": f"{tag}@{res_name}/thr={thr}",
                            "kind": "ov",
                            "prompt": prompt,
                            "threshold": thr,
                            "max_width": mw,
                            "tag": tag,
                            "res": res_name,
                        }
                    )

    fo_results: list[dict[str, Any]] = []
    print("\n== fo_signs_* (cuantitativo P/R) ==")
    print(
        f"{'arm':<36} {'n':>3} {'tp':>3} {'fp':>3} {'fn':>3} "
        f"{'P':>6} {'R':>6} {'hits':>5} {'t_s':>6}"
    )
    for arm in arms:
        tp_s = fp_s = fn_s = 0
        n_gt = 0
        n_pred = 0
        t0 = time.perf_counter()
        per_image: list[dict[str, Any]] = []
        err: Optional[str] = None
        for row in fo:
            try:
                jpeg, w, h = _jpeg_at_width(row["path"], arm["max_width"])
                if arm["kind"] == "coco":
                    preds = _predict_coco(
                        args.signs_url, jpeg, arm["threshold"], args.timeout
                    )
                else:
                    preds = _predict_ov(
                        args.ov_url,
                        jpeg,
                        arm["prompt"],
                        arm["threshold"],
                        args.timeout,
                    )
                # GT bboxes están en coords de la imagen original (hires).
                # Si resizeamos a 960, hay que escalar GT o preds. Escala preds→hires.
                if arm["max_width"] is not None:
                    frame = cv2.imread(str(row["path"]))
                    assert frame is not None
                    oh, ow = frame.shape[:2]
                    if w < ow:
                        sx, sy = ow / w, oh / h
                        for p in preds:
                            x1, y1, x2, y2 = p["bbox"]
                            p["bbox"] = [x1 * sx, y1 * sy, x2 * sx, y2 * sy]
                tp, fp, fn, _, _ = _match_pr(preds, row["bboxes"])
                tp_s += tp
                fp_s += fp
                fn_s += fn
                n_gt += len(row["bboxes"])
                n_pred += len(preds)
                per_image.append(
                    {
                        "id": row["id"],
                        "n_gt": len(row["bboxes"]),
                        "n_pred": len(preds),
                        "tp": tp,
                        "labels": [p["label"] for p in preds],
                        "scores": [round(p["score"], 3) for p in preds],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                per_image.append({"id": row["id"], "error": err})
        elapsed = time.perf_counter() - t0
        prec = tp_s / (tp_s + fp_s) if (tp_s + fp_s) else 0.0
        rec = tp_s / (tp_s + fn_s) if (tp_s + fn_s) else 0.0
        print(
            f"{arm['name']:<36} {len(fo):>3} {tp_s:>3} {fp_s:>3} {fn_s:>3} "
            f"{prec:>6.3f} {rec:>6.3f} {n_pred:>5} {elapsed:>6.1f}"
            + (f"  ERR={err}" if err else "")
        )
        fo_results.append(
            {
                **arm,
                "tp": tp_s,
                "fp": fp_s,
                "fn": fn_s,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "n_pred": n_pred,
                "n_gt": n_gt,
                "elapsed_s": round(elapsed, 2),
                "per_image": per_image,
                "error": err,
            }
        )

    ar_results: list[dict[str, Any]] = []
    print("\n== AR cualitativo (hit box a ojo; SIN P/R) ==")
    if not ar:
        print("  (pendiente — sin fotos AR)")
    else:
        # Solo candidato recomendable: OV-A thr barrido @960 + hires summary
        ar_arms = [a for a in arms if a["kind"] == "ov"]
        print(f"{'arm':<36} {'file':<28} {'hits':>5} {'labels/scores'}")
        for path in ar:
            for arm in ar_arms:
                try:
                    jpeg, _, _ = _jpeg_at_width(path, arm["max_width"])
                    preds = _predict_ov(
                        args.ov_url,
                        jpeg,
                        arm["prompt"],
                        arm["threshold"],
                        args.timeout,
                    )
                    labels = [f"{p['label']}:{p['score']:.2f}" for p in preds]
                    hit = "HIT" if preds else "MISS"
                    print(
                        f"{arm['name']:<36} {path.name:<28} {len(preds):>5} "
                        f"{hit} {labels}"
                    )
                    ar_results.append(
                        {
                            "file": path.name,
                            "arm": arm["name"],
                            "hits": len(preds),
                            "qualitative": hit,
                            "labels": [p["label"] for p in preds],
                            "scores": [round(p["score"], 3) for p in preds],
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"{arm['name']:<36} {path.name:<28} ERROR {exc}")
                    ar_results.append(
                        {"file": path.name, "arm": arm["name"], "error": str(exc)}
                    )

    # Recomendación automática (fo_signs only; no mezclar AR).
    print("\n== recomendación (solo fo_signs; gate humano confirma) ==")
    ov_fo = [
        r
        for r in fo_results
        if r.get("kind") == "ov" and r.get("error") is None and r.get("res") == "960"
    ]
    best = None
    if ov_fo:
        # Prioriza recall, luego precision, luego thr más alto (menos ruido).
        best = max(
            ov_fo,
            key=lambda r: (r["recall"], r["precision"], r["threshold"]),
        )
        print(
            f"  SIGNS_OV_PROMPT={best['prompt']!r}  "
            f"(tag {best.get('tag')})"
        )
        print(f"  SIGNS_OV_THRESHOLD={best['threshold']}  "
              f"(P={best['precision']:.3f} R={best['recall']:.3f} @960)")
    else:
        print("  SIGNS_OV_PROMPT='traffic sign' (fallback; medición incompleta)")
        print("  SIGNS_OV_THRESHOLD=pending (medir cuando :8093 healthy)")

    # Veredicto resolución: comparar best prompt@best thr 960 vs hires
    print("\n== veredicto resolución ==")
    res_verdict = "unknown"
    if best:
        hires = next(
            (
                r
                for r in fo_results
                if r.get("kind") == "ov"
                and r.get("prompt") == best["prompt"]
                and r.get("threshold") == best["threshold"]
                and r.get("res") == "hires"
            ),
            None,
        )
        if hires:
            print(
                f"  OV@960  R={best['recall']:.3f} P={best['precision']:.3f}"
            )
            print(
                f"  OV@hires R={hires['recall']:.3f} P={hires['precision']:.3f}"
            )
            if best["recall"] >= 0.5 and best["recall"] >= (hires["recall"] - 0.05):
                res_verdict = (
                    "cerrar_frame: OV@960 alcanza; no tocar BRIDGE_MAX_WIDTH/tiling"
                )
            elif hires["recall"] > best["recall"] + 0.1:
                res_verdict = (
                    "reabrir_pixeles: OV@960 flojo pero hires levanta → "
                    "considerar tiling / subir BRIDGE_MAX_WIDTH (decisión aparte)"
                )
            else:
                res_verdict = (
                    "indeterminado: ni 960 ni hires dominan con margen claro"
                )
            print(f"  -> {res_verdict}")
        else:
            print("  sin par hires para el best@960")
    else:
        print("  sin best OV@960 — veredicto pending")

    report = {
        "signs_url": args.signs_url,
        "ov_url": args.ov_url,
        "signs_healthy": signs_ok,
        "ov_healthy": ov_ok,
        "fo_signs_count": len(fo),
        "ar_count": len(ar),
        "ar_pending": len(ar) == 0,
        "fo_results": fo_results,
        "ar_results": ar_results,
        "recommendation": {
            "SIGNS_OV_PROMPT": best["prompt"] if best else "traffic sign",
            "SIGNS_OV_THRESHOLD": best["threshold"] if best else None,
            "note": (
                "propuesto por medición fo_signs@960; gate humano confirma"
                if best
                else "pending — OV no midió"
            ),
        },
        "resolution_verdict": res_verdict,
        "builder": "detection.common.paddlex_client.build_open_vocab_body",
    }
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nReport -> {args.report}")
    return 0 if ov_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
