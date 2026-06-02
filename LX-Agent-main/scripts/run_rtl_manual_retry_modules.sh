#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${SCRIPT_DIR}/run_rtl_manual_full.sh" \
  --skip-build \
  --skip-main-enhance \
  --retryable-modules \
  --no-force \
  "$@"
