#!/usr/bin/env python3
"""A/B ENABLE_EVIDENCE_CASCADE on vs off over imagenes_muestra.

Measures wall latency of bridge.run_detections and detection-count deltas
for dependents (pedestrians attrs / face_id / open_vocab). Also estimates
recall risk of conditioning faces←person and signs←person|vehicle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

# Host-side URLs before importing detection/bridge (module-level getenv).
_HOST_ENV = {
    "ADAPTER_INGEST_URL": "http://127.0.0.1:8000/ingest",
    "ADAPTER_MEDIA_CURRENT_URL": "http://127.0.0.1:8000/media/current",
    "ADAPTER_PREVIEW_FRAME_URL": "http://127.0.0.1:8000/preview/frame",
    "ADAPTER_CAPABILITIES_URL": "http://127.0.0.1:8000/capabilities",
    "PADDLEX_URL": "http://127.0.0.1:8080",
    "PADDLEX_OCR_URL": "http://127.0.0.1:8081",
    "PADDLEX_OBJECTS_URL": "http://127.0.0.1:8082",
    "PADDLEX_FACES_URL": "http://127.0.0.1:8083",
    "PADDLEX_PEDESTRIANS_URL": "http://127.0.0.1:8084",
    "PADDLEX_SCENE_URL": "http://127.0.0.1:8085",
    "PADDLEX_POSE_URL": "http://127.0.0.1:8086",
    "PADDLEX_FACE_ID_URL": "http://127.0.0.1:8087",
    "PADDLEX_SIGNS_URL": "http://127.0.0.1:8088",
    "PADDLEX_SIGNS_OV_URL": "http://127.0.0.1:8093",
    "PADDLEX_SCENE_CLS_URL": "http://127.0.0.1:8089",
    "PADDLEX_INSTANCES_URL": "http://127.0.0.1:8090",
    "PADDLEX_SMALL_OBJECTS_URL": "http://127.0.0.1:8091",
    "PADDLEX_ANOMALY_URL": "http://127.0.0.1:8092",
    "PADDLEX_OPEN_VOCAB_URL": "http://127.0.0.1:8093",
    "ENABLE_FACE_DETECTION": "true",
    "ENABLE_PEDESTRIAN_ATTRS": "true",
    "ENABLE_FACE_ID": "true",
    "ENABLE_OPEN_VOCAB": "true",
    "ENABLE_SIGNS": "true",
    "ENABLE_POSE": "true",
    "ENABLE_SCENE_SEG": "true",
    "ENABLE_SCENE_OCR": "true",
    "ENABLE_SCENE_CLS": "true",
    "ENABLE_INSTANCE_SEG": "true",
    "ENABLE_SMALL_OBJECTS": "true",
    "ENABLE_ANOMALY": "true",
    "ENABLE_PLATE_OCR": "true",
    "CASCADE_OBJECT_LOW_SCORE": os.getenv("CASCADE_OBJECT_LOW_SCORE", "0.35"),
}
for k, v in _HOST_ENV.items():
    os.environ.setdefault(k, v)

import cv2  # noqa: E402
import httpx  # noqa: E402

from bridge.cascade import (  # noqa: E402
    CascadeConfig,
    decide_dependent_caps,
    has_face_evidence,
    has_person_evidence,
)
import bridge.main as bridge_main  # noqa: E402
from bridge.main import run_detections  # noqa: E402
from detection.registry import CAPABILITIES, reset_all_trackers  # noqa: E402

MEDIA = Path(os.getenv("CASCADE_MEDIA", str(_REPO / "imagenes_muestra")))
REPORT = Path(os.getenv("REPORT", str(_REPO / "scripts/eval_report_cascade_ab.json")))
MAX_PER_PREFIX = int(os.getenv("CASCADE_MAX_PER_PREFIX", "4"))
PAUSE_S = float(os.getenv("CASCADE_PAUSE_S", "0.15"))
TIMEOUT = float(os.getenv("CASCADE_HTTP_TIMEOUT", "120"))
# Caps relevantes a cascada + candidatos faces/signs. Evita scene/instances/…
# (latencia dominada por experimental no aporta al veredicto).
_DEFAULT_ACTIVE = (
    "vehicles,objects,faces,pedestrians,face_id,open_vocab,signs,pose"
)
ACTIVE_CAPS = {
    x.strip()
    for x in os.getenv("CASCADE_ACTIVE_CAPS", _DEFAULT_ACTIVE).split(",")
    if x.strip()
}

# Packs that stress dependents / conditioning candidates.
FOCUS_PREFIXES = (
    "fo_pedestrians",
    "fo_faces",
    "fo_face_id",
    "fo_open_vocab",
    "fo_signs",
    "fo_objects",
    "fo_vehicles",
    "fo_pose",
    "fo_anomaly",
)

VEHICLEISH = frozenset(
    {
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
        "train",
        "boat",
        "airplane",
    }
)

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("measure_cascade_ab")


def _entity(det: dict[str, Any]) -> str:
    return str(det.get("entity_type") or det.get("label") or "").strip().lower()


def _count_by_entity(dets: list[dict[str, Any]] | None) -> Counter[str]:
    c: Counter[str] = Counter()
    if not dets:
        return c
    for d in dets:
        if isinstance(d, dict):
            e = _entity(d)
            if e:
                c[e] += 1
    return c


def _has_person_attrs(dets: list[dict[str, Any]] | None) -> bool:
    if not dets:
        return False
    for d in dets:
        if not isinstance(d, dict):
            continue
        if _entity(d) != "person" and str(d.get("label") or "").lower() != "person":
            continue
        attrs = d.get("attributes") or d.get("attrs")
        if attrs:
            return True
    return False


def _object_labels(dets: list[dict[str, Any]] | None) -> set[str]:
    out: set[str] = set()
    if not dets:
        return out
    for d in dets:
        if not isinstance(d, dict):
            continue
        if _entity(d) not in ("object", "person", "") and "label" not in d:
            continue
        lab = str(d.get("label") or "").strip().lower()
        if lab:
            out.add(lab)
    return out


def select_images() -> list[Path]:
    paths: list[Path] = []
    for prefix in FOCUS_PREFIXES:
        matches = sorted(MEDIA.glob(f"{prefix}_*.jpg")) + sorted(
            MEDIA.glob(f"{prefix}_*.png")
        )
        if MAX_PER_PREFIX > 0:
            matches = matches[:MAX_PER_PREFIX]
        paths.extend(matches)
    # de-dupe preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


async def one_run(
    client: httpx.AsyncClient, frame, *, cascade: bool
) -> tuple[float, list[dict[str, Any]] | None, bool]:
    os.environ["ENABLE_EVIDENCE_CASCADE"] = "true" if cascade else "false"
    reset_all_trackers()
    t0 = time.perf_counter()
    dets, degraded, _preview = await run_detections(client, frame)
    elapsed = time.perf_counter() - t0
    return elapsed, dets, degraded


def summarize(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"n": 0}
    xs_s = sorted(xs)
    n = len(xs_s)
    return {
        "n": n,
        "mean_s": round(statistics.mean(xs_s), 3),
        "median_s": round(statistics.median(xs_s), 3),
        "p90_s": round(xs_s[min(n - 1, int(0.9 * (n - 1)))], 3),
        "min_s": round(xs_s[0], 3),
        "max_s": round(xs_s[-1], 3),
    }


async def main() -> int:
    images = select_images()
    if not images:
        print(f"No images under {MEDIA}", file=sys.stderr)
        return 2

    # Pin SPA-active set so A/B is comparable and not drowned by experimental.
    async def _fixed_active(_client: httpx.AsyncClient) -> set[str]:
        return set(ACTIVE_CAPS)

    bridge_main.fetch_active_capability_names = _fixed_active  # type: ignore[method-assign]

    print(
        f"cascade A/B images={len(images)} max_per_prefix={MAX_PER_PREFIX} "
        f"active={sorted(ACTIVE_CAPS)} media={MEDIA}"
    )

    rows: list[dict[str, Any]] = []
    lat_on: list[float] = []
    lat_off: list[float] = []

    # Aggregate presence for dependents (cascade off = oracle "always run").
    dep_keys = ("person_attrs", "face", "face_id", "open_vocab", "sign")
    present_off: Counter[str] = Counter()
    present_on: Counter[str] = Counter()
    lost_on: Counter[str] = Counter()  # present off, absent on

    # Counterfactual: if faces←person / signs←person|vehicle
    faces_hit_no_person = 0
    faces_hit_with_person = 0
    faces_hit_total = 0
    signs_hit_no_street = 0
    signs_hit_with_street = 0
    signs_hit_total = 0

    wave2_skip_rates: Counter[str] = Counter()  # ped|fid|ov skipped under ON
    wave2_run_rates: Counter[str] = Counter()
    objects_states: Counter[str] = Counter()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Warmup (ON) — discard
        warm = cv2.imread(str(images[0]))
        if warm is not None:
            await one_run(client, warm, cascade=True)
            await asyncio.sleep(PAUSE_S)

        for i, path in enumerate(images, 1):
            frame = cv2.imread(str(path))
            if frame is None:
                print(f"  skip unreadable {path.name}")
                continue

            # OFF first (full gather), then ON — same image, pause between.
            t_off, dets_off, deg_off = await one_run(client, frame, cascade=False)
            await asyncio.sleep(PAUSE_S)
            t_on, dets_on, deg_on = await one_run(client, frame, cascade=True)
            await asyncio.sleep(PAUSE_S)

            lat_off.append(t_off)
            lat_on.append(t_on)

            c_off = _count_by_entity(dets_off)
            c_on = _count_by_entity(dets_on)

            flags_off = {
                "person_attrs": _has_person_attrs(dets_off),
                "face": c_off.get("face", 0) > 0,
                "face_id": c_off.get("face_id", 0) > 0,
                "open_vocab": c_off.get("open_vocab", 0) > 0
                or c_off.get("ov", 0) > 0,
                "sign": c_off.get("sign", 0) > 0,
            }
            flags_on = {
                "person_attrs": _has_person_attrs(dets_on),
                "face": c_on.get("face", 0) > 0,
                "face_id": c_on.get("face_id", 0) > 0,
                "open_vocab": c_on.get("open_vocab", 0) > 0
                or c_on.get("ov", 0) > 0,
                "sign": c_on.get("sign", 0) > 0,
            }
            for k in dep_keys:
                if flags_off[k]:
                    present_off[k] += 1
                if flags_on[k]:
                    present_on[k] += 1
                if flags_off[k] and not flags_on[k]:
                    lost_on[k] += 1

            # Rebuild objects/faces evidence from OFF dets for policy stats +
            # counterfactuals (OFF always ran dependents).
            # Use objects labels from merged dets (entity object/person).
            labels = set()
            faces_raw_proxy: list[dict] = []
            object_raw_proxy: list[dict] = []
            if dets_off:
                for d in dets_off:
                    if not isinstance(d, dict):
                        continue
                    et = _entity(d)
                    lab = str(d.get("label") or "").strip().lower()
                    if et == "face":
                        faces_raw_proxy.append(d)
                    if et in ("object", "person") or lab:
                        if et in ("object", "person") or lab in VEHICLEISH | {"person"}:
                            object_raw_proxy.append(
                                {
                                    "label": lab or et,
                                    "score": d.get("score", d.get("confidence")),
                                }
                            )
                            if lab:
                                labels.add(lab)

            person = has_person_evidence(object_raw_proxy) or ("person" in labels)
            face = has_face_evidence(faces_raw_proxy)
            street = person or bool(labels & VEHICLEISH)

            cfg = CascadeConfig(enabled=True, object_low_score=float(
                os.getenv("CASCADE_OBJECT_LOW_SCORE", "0.35")
            ))
            decision = decide_dependent_caps(
                config=cfg,
                objects_active=True,
                object_raw=object_raw_proxy,
                faces_raw=faces_raw_proxy,
                open_vocab_in_gather=True,
                pedestrians_in_gather=True,
                face_id_in_gather=True,
            )
            objects_states[decision.objects_state.value] += 1
            for name, ran in (
                ("pedestrians", decision.run_pedestrians),
                ("face_id", decision.run_face_id),
                ("open_vocab", decision.run_open_vocab),
            ):
                if ran:
                    wave2_run_rates[name] += 1
                else:
                    wave2_skip_rates[name] += 1

            if flags_off["face"]:
                faces_hit_total += 1
                if person:
                    faces_hit_with_person += 1
                else:
                    faces_hit_no_person += 1
            if flags_off["sign"]:
                signs_hit_total += 1
                if street:
                    signs_hit_with_street += 1
                else:
                    signs_hit_no_street += 1

            row = {
                "image": path.name,
                "t_off_s": round(t_off, 3),
                "t_on_s": round(t_on, 3),
                "delta_s": round(t_on - t_off, 3),
                "degraded_off": deg_off,
                "degraded_on": deg_on,
                "n_off": len(dets_off or []),
                "n_on": len(dets_on or []),
                "lost": [k for k in dep_keys if flags_off[k] and not flags_on[k]],
                "wave2": {
                    "pedestrians": decision.run_pedestrians,
                    "face_id": decision.run_face_id,
                    "open_vocab": decision.run_open_vocab,
                    "objects_state": decision.objects_state.value,
                },
                "counterfactual": {
                    "person": person,
                    "face": face,
                    "street": street,
                },
            }
            rows.append(row)
            print(
                f"[{i}/{len(images)}] {path.name}: "
                f"off={t_off:.2f}s on={t_on:.2f}s d={t_on - t_off:+.2f}s "
                f"lost={row['lost'] or '-'}"
            )

    n = len(rows)
    speedup = None
    if lat_off and statistics.mean(lat_off) > 0:
        speedup = round(
            (statistics.mean(lat_off) - statistics.mean(lat_on))
            / statistics.mean(lat_off),
            3,
        )

    faces_risk = (
        round(faces_hit_no_person / faces_hit_total, 3) if faces_hit_total else None
    )
    signs_risk = (
        round(signs_hit_no_street / signs_hit_total, 3) if signs_hit_total else None
    )

    # Decision heuristics (documented in report).
    decide_faces = "keep_wave1"
    if faces_risk is not None and faces_risk <= 0.05 and faces_hit_total >= 5:
        decide_faces = "candidate_condition_on_person"
    elif faces_risk is not None and faces_risk > 0.15:
        decide_faces = "do_not_condition_on_person"

    decide_signs = "keep_wave1"
    if signs_risk is not None and signs_risk <= 0.05 and signs_hit_total >= 3:
        decide_signs = "candidate_condition_on_street"
    elif signs_risk is not None and signs_risk > 0.15:
        decide_signs = "do_not_condition_on_street"
    elif signs_hit_total < 3:
        decide_signs = "insufficient_signs_fixtures"

    report = {
        "n_images": n,
        "max_per_prefix": MAX_PER_PREFIX,
        "focus_prefixes": list(FOCUS_PREFIXES),
        "latency": {
            "cascade_off": summarize(lat_off),
            "cascade_on": summarize(lat_on),
            "mean_delta_on_minus_off_s": round(
                statistics.mean(lat_on) - statistics.mean(lat_off), 3
            )
            if lat_on and lat_off
            else None,
            "mean_speedup_frac": speedup,
        },
        "dependent_presence": {
            "off": dict(present_off),
            "on": dict(present_on),
            "lost_when_cascade_on": dict(lost_on),
        },
        "wave2_policy_from_off_proxy": {
            "objects_states": dict(objects_states),
            "run": dict(wave2_run_rates),
            "skip": dict(wave2_skip_rates),
            "skip_rate": {
                k: round(wave2_skip_rates[k] / n, 3)
                for k in ("pedestrians", "face_id", "open_vocab")
                if n
            },
        },
        "condition_faces_on_person": {
            "faces_hit_total": faces_hit_total,
            "faces_hit_with_person": faces_hit_with_person,
            "faces_hit_no_person": faces_hit_no_person,
            "fraction_lost_if_conditioned": faces_risk,
            "verdict": decide_faces,
        },
        "condition_signs_on_street": {
            "trigger": "person OR vehicleish COCO label in merged dets",
            "signs_hit_total": signs_hit_total,
            "signs_hit_with_street": signs_hit_with_street,
            "signs_hit_no_street": signs_hit_no_street,
            "fraction_lost_if_conditioned": signs_risk,
            "verdict": decide_signs,
        },
        "caps_in_registry": [c.name for c in CAPABILITIES],
        "active_caps": sorted(ACTIVE_CAPS),
        "rows": rows,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(json.dumps({k: report[k] for k in report if k != "rows"}, indent=2))
    print(f"\nWrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
