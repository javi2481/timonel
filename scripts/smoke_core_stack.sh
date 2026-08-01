#!/usr/bin/env bash
# Smoke integración Core (bridge → adapter → /events → preview).
# Uso: ./scripts/smoke_core_stack.sh
# OCR on: EXPECT_PLATE_OCR=true ./scripts/smoke_core_stack.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export ADAPTER_URL="${ADAPTER_URL:-http://127.0.0.1:8000}"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
exec "$PY" scripts/smoke_core_stack.py "$@"
