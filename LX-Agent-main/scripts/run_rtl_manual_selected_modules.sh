#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_rtl_manual_selected_modules.sh <module_a,module_b> [run_rtl_manual_full.sh options]

Example:
  scripts/run_rtl_manual_selected_modules.sh decode,writeback
  scripts/run_rtl_manual_selected_modules.sh decode --top-module arm_soc_top
EOF
}

if [[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

MODULES="$1"
shift

exec "${SCRIPT_DIR}/run_rtl_manual_full.sh" \
  --skip-build \
  --skip-main-enhance \
  --modules "${MODULES}" \
  --no-force \
  "$@"
