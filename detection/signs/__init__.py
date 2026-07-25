"""Señales de tránsito (YOLO-World OV por default; COCO legacy opt-in)."""

from detection.signs.client import (
    ENABLE_SIGNS,
    PADDLEX_SIGNS_OV_URL,
    PADDLEX_SIGNS_URL,
    SIGNS_BACKEND,
    SIGNS_OV_PROMPT,
    SIGNS_OV_THRESHOLD,
    SIGNS_THRESHOLD,
    SIGN_LABELS,
    infer_signs,
    normalize_signs_result,
    reset_signs_tracker,
)

__all__ = [
    "ENABLE_SIGNS",
    "PADDLEX_SIGNS_OV_URL",
    "PADDLEX_SIGNS_URL",
    "SIGNS_BACKEND",
    "SIGNS_OV_PROMPT",
    "SIGNS_OV_THRESHOLD",
    "SIGNS_THRESHOLD",
    "SIGN_LABELS",
    "infer_signs",
    "normalize_signs_result",
    "reset_signs_tracker",
]
