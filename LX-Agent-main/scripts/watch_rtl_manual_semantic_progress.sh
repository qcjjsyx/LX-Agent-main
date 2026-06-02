#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="./rtl"
TOP_MODULE="arm_soc_top"

usage() {
  cat <<'EOF'
Usage:
  scripts/watch_rtl_manual_semantic_progress.sh [options]

Options:
  --project-root <path>   Default: ./rtl
  --top-module <name>     Default: arm_soc_top
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --top-module)
      TOP_MODULE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

PROGRESS_FILE="${PROJECT_ROOT}/knowledge_ir/${TOP_MODULE}/semantic/semantic_progress.jsonl"

echo "Watching ${PROGRESS_FILE}"
mkdir -p "$(dirname "${PROGRESS_FILE}")"
touch "${PROGRESS_FILE}"
tail -f "${PROGRESS_FILE}"
