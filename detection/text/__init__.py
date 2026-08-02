"""OCR de escena / carteles (no solo patentes)."""

from detection.text.client import (
    ENABLE_SCENE_OCR,
    SCENE_OCR_FROM_SIGNS,
    SCENE_OCR_MIN_SCORE,
    enrich_text_from_sign_crops,
    infer_scene_ocr,
    normalize_scene_ocr_result,
)

__all__ = [
    "ENABLE_SCENE_OCR",
    "SCENE_OCR_FROM_SIGNS",
    "SCENE_OCR_MIN_SCORE",
    "enrich_text_from_sign_crops",
    "infer_scene_ocr",
    "normalize_scene_ocr_result",
]
