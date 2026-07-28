"""Política pura de cascada por evidencia (sin HTTP ni merge).

Clasifica el resultado de objects y selecciona capacidades dependientes.
Scores solo se comparan dentro del mismo detector (COCO objects).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Optional

# Capacidades que en MVP se ejecutan en 2ª oleada tras oleada 1.
# pedestrians/face_id: gated por evidencia. open_vocab corre en oleada 1
# (cola larga en paralelo con objects).
DEPENDENT_CAP_NAMES: frozenset[str] = frozenset({"pedestrians", "face_id"})

# Independientes: corren en 1ª oleada si SPA-active (o vehicles siempre).
# faces/pose/signs/etc. NO se condicionan aún (estrategia conservadora).


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class CascadeConfig:
    enabled: bool
    object_low_score: float

    @classmethod
    def from_env(cls) -> CascadeConfig:
        return cls(
            enabled=_env_bool("ENABLE_EVIDENCE_CASCADE", "false"),
            object_low_score=float(os.getenv("CASCADE_OBJECT_LOW_SCORE", "0.35")),
        )


class ObjectsEvidenceState(str, Enum):
    DISABLED = "disabled"
    FAILED = "failed"
    EMPTY = "empty"
    LOW_CONFIDENCE = "low_confidence"
    HITS = "hits"


@dataclass(frozen=True)
class CascadeDecision:
    """Qué dependencias correr en la 2ª oleada y por qué."""

    run_pedestrians: bool
    run_face_id: bool
    run_open_vocab: bool
    objects_state: ObjectsEvidenceState
    reasons: tuple[str, ...]


def _safe_score(det: Any) -> Optional[float]:
    if not isinstance(det, dict):
        return None
    raw = det.get("score", det.get("conf", det.get("confidence")))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def classify_objects_evidence(
    object_raw: Any,
    *,
    objects_active: bool,
    low_score: float,
) -> ObjectsEvidenceState:
    """Estado de objects usando solo scores COCO del propio detector.

    objects_active=False → DISABLED (no dispara open_vocab).
    None → FAILED; [] → EMPTY; max(score)<low → LOW_CONFIDENCE; else HITS.
    Detecciones sin score válido se ignoran al calcular max.
    """
    if not objects_active:
        return ObjectsEvidenceState.DISABLED
    if object_raw is None:
        return ObjectsEvidenceState.FAILED
    if not isinstance(object_raw, list):
        return ObjectsEvidenceState.FAILED
    if len(object_raw) == 0:
        return ObjectsEvidenceState.EMPTY

    scores: list[float] = []
    for det in object_raw:
        s = _safe_score(det)
        if s is not None:
            scores.append(s)

    if not scores:
        # Hits sin score usable: tratar como low_confidence (segunda opinión).
        return ObjectsEvidenceState.LOW_CONFIDENCE
    if max(scores) < low_score:
        return ObjectsEvidenceState.LOW_CONFIDENCE
    return ObjectsEvidenceState.HITS


def has_person_evidence(
    object_raw: Any,
    *,
    min_score: float = 0.0,
) -> bool:
    """True si objects devolvió al menos un label==person con score >= min_score."""
    if not isinstance(object_raw, list):
        return False
    for det in object_raw:
        if not isinstance(det, dict):
            continue
        label = str(det.get("label") or "").strip().lower()
        if label != "person":
            continue
        s = _safe_score(det)
        if s is None:
            # person sin score: contar como evidencia (no bloquear attrs).
            return True
        if s >= min_score:
            return True
    return False


def has_face_evidence(faces_raw: Any) -> bool:
    """True si faces devolvió al menos una detección (lista no vacía)."""
    if not isinstance(faces_raw, list):
        return False
    return len(faces_raw) > 0


def needs_open_vocab_second_opinion(state: ObjectsEvidenceState) -> bool:
    return state in (
        ObjectsEvidenceState.FAILED,
        ObjectsEvidenceState.EMPTY,
        ObjectsEvidenceState.LOW_CONFIDENCE,
    )


def decide_dependent_caps(
    *,
    config: CascadeConfig,
    objects_active: bool,
    object_raw: Any,
    faces_raw: Any,
    open_vocab_in_gather: bool,
    pedestrians_in_gather: bool,
    face_id_in_gather: bool,
) -> CascadeDecision:
    """Selecciona dependientes de la 2ª oleada.

    *_in_gather: la capacidad pasó filter_capabilities (SPA-active / always).
    La evidencia es ortogonal al permiso: sin evidencia no se llama.
    """
    reasons: list[str] = []
    state = classify_objects_evidence(
        object_raw,
        objects_active=objects_active,
        low_score=config.object_low_score,
    )
    reasons.append(f"objects_state={state.value}")

    if not config.enabled:
        return CascadeDecision(
            run_pedestrians=False,
            run_face_id=False,
            run_open_vocab=False,
            objects_state=state,
            reasons=("cascade=disabled",) + tuple(reasons),
        )

    person = has_person_evidence(object_raw)
    face = has_face_evidence(faces_raw)

    run_ped = False
    if pedestrians_in_gather:
        if person:
            run_ped = True
            reasons.append("pedestrians=person")
        else:
            reasons.append("pedestrians=no_person")
    else:
        reasons.append("pedestrians=inactive")

    run_fid = False
    if face_id_in_gather:
        if face:
            run_fid = True
            reasons.append("face_id=face")
        else:
            reasons.append("face_id=no_face")
    else:
        reasons.append("face_id=inactive")

    # Cola larga: OV corre siempre que esté available (no solo si COCO falló).
    run_ov = False
    if open_vocab_in_gather:
        # OV corre en oleada 1 (DEPENDENT_CAP_NAMES); no re-disparar en wave2.
        reasons.append("open_vocab=wave1")
    else:
        reasons.append("open_vocab=inactive")

    return CascadeDecision(
        run_pedestrians=run_ped,
        run_face_id=run_fid,
        run_open_vocab=run_ov,
        objects_state=state,
        reasons=tuple(reasons),
    )


def wave1_capability_names(
    eligible_names: Iterable[str],
    *,
    cascade_enabled: bool,
) -> set[str]:
    """Nombres a ejecutar en oleada 1.

    Con cascada: todo eligible excepto DEPENDENT_CAP_NAMES.
    Sin cascada: todos (caller usa gather único).
    """
    names = set(eligible_names)
    if not cascade_enabled:
        return names
    return names - DEPENDENT_CAP_NAMES


def dependent_names_from_decision(decision: CascadeDecision) -> set[str]:
    out: set[str] = set()
    if decision.run_pedestrians:
        out.add("pedestrians")
    if decision.run_face_id:
        out.add("face_id")
    if decision.run_open_vocab:
        out.add("open_vocab")
    return out


__all__ = [
    "CascadeConfig",
    "CascadeDecision",
    "DEPENDENT_CAP_NAMES",
    "ObjectsEvidenceState",
    "classify_objects_evidence",
    "decide_dependent_caps",
    "dependent_names_from_decision",
    "has_face_evidence",
    "has_person_evidence",
    "needs_open_vocab_second_opinion",
    "wave1_capability_names",
]
