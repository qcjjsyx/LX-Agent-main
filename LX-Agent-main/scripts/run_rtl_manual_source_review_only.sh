#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${SCRIPT_DIR}/run_rtl_manual_full.sh" \
  --skip-build \
  --with-source-review \
  --skip-main-enhance \
  --skip-modules-enhance \
  --skip-compose \
  --no-force \
  "$@"
