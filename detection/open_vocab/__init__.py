"""Open-vocabulary detection (stack default)."""

from detection.open_vocab.client import (
    ENABLE_OPEN_VOCAB,
    OPEN_VOCAB_PROMPT,
    infer_open_vocab,
    normalize_open_vocab_result,
)

__all__ = [
    "ENABLE_OPEN_VOCAB",
    "OPEN_VOCAB_PROMPT",
    "infer_open_vocab",
    "normalize_open_vocab_result",
]
