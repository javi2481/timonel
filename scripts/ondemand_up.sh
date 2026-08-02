#!/usr/bin/env bash
# Deprecated: use full_up.sh (all capabilities up at boot).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "ondemand_up is deprecated → scripts/full_up.sh"
exec "$ROOT/scripts/full_up.sh"
