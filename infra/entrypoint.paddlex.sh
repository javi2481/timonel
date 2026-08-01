#!/bin/sh
# TIMONEL_PIPELINE/TIMONEL_PORT parametrizan la misma imagen para servir distintos
# pipelines PaddleX (attr por default, OCR via servicio paddlex-ocr).
# TIMONEL_USE_HPIP=1 añade --use_hpip (tras instalar hpi-cpu y validar ≥~1.5×).
# TIMONEL_DEVICE=gpu exige nvidia-smi usable antes de arrancar el serve.
set -eu
HPIP_ARGS=""
case "${TIMONEL_USE_HPIP:-0}" in
  1|true|TRUE|yes|YES) HPIP_ARGS="--use_hpip" ;;
esac

DEVICE="${TIMONEL_DEVICE:-cpu}"
case "${DEVICE}" in
  gpu|GPU)
    if ! command -v nvidia-smi >/dev/null 2>&1; then
      echo "entrypoint: TIMONEL_DEVICE=gpu but nvidia-smi not found in image/runtime" >&2
      exit 1
    fi
    if ! nvidia-smi >/dev/null 2>&1; then
      echo "entrypoint: TIMONEL_DEVICE=gpu but nvidia-smi failed (GPU/runtime unavailable)" >&2
      exit 1
    fi
    ;;
esac

exec paddlex --serve \
  --pipeline "${TIMONEL_PIPELINE:-vehicle_attribute_recognition}" \
  --port "${TIMONEL_PORT:-8080}" \
  --device "${DEVICE}" \
  ${HPIP_ARGS}
