#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/ML/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-python}"
fi

PROJECT_ROOT="./rtl"
RTL_INPUTS="rtl"
TOP_MODULE="arm_soc_top"
MODEL="deepseek-v4-pro"
REVIEW_MODEL="deepseek-v4-flash"
KNOWLEDGE_TIMEOUT="10800"
MODULE_FILTER="all"
MODULES=""
WITH_SOURCE_REVIEW=0
NO_FORCE=0
SKIP_MAIN_ENHANCE=0
SKIP_MODULES_ENHANCE=0
SKIP_BUILD=0
SKIP_COMPOSE=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_rtl_manual_full.sh [options]

Options:
  --project-root <path>        Default: ./rtl
  --rtl-inputs <path>          Default: rtl
  --top-module <name>          Default: arm_soc_top
  --model <name>               Enhancement model. Default: deepseek-v4-pro
  --review-model <name>        Source-review/final-review model. Default: deepseek-v4-flash
  --knowledge-timeout <sec>    Default: 10800
  --with-source-review         Run source-review after build, then enhance from updated Manual Context
  --module-filter <filter>     all|pending|missing|stale|failed|invalid|success|retryable|not-success
  --retryable-modules          Shortcut for --module-filter retryable
  --modules <a,b,c>            Enhance only these modules instead of all selected modules
  --skip-build                 Skip build/rebuild and use existing base artifacts
  --skip-main-enhance          Skip main manual enhancement
  --skip-modules-enhance       Skip module page enhancement
  --skip-compose               Skip compose/review at the end
  --no-force                   Reuse valid build artifacts instead of forcing build regeneration
  --python <path>              Python executable. Can also set PYTHON_BIN
  -h, --help                   Show this help

Examples:
  scripts/run_rtl_manual_full.sh
  scripts/run_rtl_manual_full.sh --with-source-review
  scripts/run_rtl_manual_full.sh --retryable-modules
  scripts/run_rtl_manual_full.sh --modules decode,writeback
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --rtl-inputs)
      RTL_INPUTS="$2"
      shift 2
      ;;
    --top-module)
      TOP_MODULE="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --review-model)
      REVIEW_MODEL="$2"
      shift 2
      ;;
    --knowledge-timeout)
      KNOWLEDGE_TIMEOUT="$2"
      shift 2
      ;;
    --with-source-review)
      WITH_SOURCE_REVIEW=1
      shift
      ;;
    --module-filter)
      MODULE_FILTER="$2"
      shift 2
      ;;
    --retryable-modules)
      MODULE_FILTER="retryable"
      shift
      ;;
    --modules)
      MODULES="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --skip-main-enhance)
      SKIP_MAIN_ENHANCE=1
      shift
      ;;
    --skip-modules-enhance)
      SKIP_MODULES_ENHANCE=1
      shift
      ;;
    --skip-compose)
      SKIP_COMPOSE=1
      shift
      ;;
    --no-force)
      NO_FORCE=1
      shift
      ;;
    --python)
      PYTHON_BIN="$2"
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

run() {
  printf '\n>>>'
  printf ' %q' "$@"
  printf '\n'
  "$@"
}

build_args=(
  "${PYTHON_BIN}" -m backend.manual_cli build
  --project-root "${PROJECT_ROOT}"
  --rtl-inputs "${RTL_INPUTS}"
  --top-module "${TOP_MODULE}"
  --knowledge-timeout "${KNOWLEDGE_TIMEOUT}"
  --log-events
)
if [[ "${NO_FORCE}" -eq 0 ]]; then
  build_args+=(--force)
fi

run "${PYTHON_BIN}" -m backend.manual_cli status \
  --project-root "${PROJECT_ROOT}" \
  --top-module "${TOP_MODULE}" \
  --log-events

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
  run "${build_args[@]}"
else
  echo "Skip build: using existing base artifacts."
fi

if [[ "${WITH_SOURCE_REVIEW}" -eq 1 ]]; then
  run "${PYTHON_BIN}" -m backend.manual_cli source-review \
    --project-root "${PROJECT_ROOT}" \
    --top-module "${TOP_MODULE}" \
    --model "${REVIEW_MODEL}" \
    --log-events
  echo "Skip post source-review build: source-review writes Manual Context directly; rerun enhance/compose next."
fi

if [[ "${SKIP_MAIN_ENHANCE}" -eq 0 ]]; then
  run "${PYTHON_BIN}" -m backend.manual_cli enhance \
    --project-root "${PROJECT_ROOT}" \
    --top-module "${TOP_MODULE}" \
    --main-manual \
    --model "${MODEL}" \
    --log-events
fi

if [[ "${SKIP_MODULES_ENHANCE}" -eq 0 ]]; then
  if [[ -n "${MODULES}" ]]; then
    run "${PYTHON_BIN}" -m backend.manual_cli enhance \
      --project-root "${PROJECT_ROOT}" \
      --top-module "${TOP_MODULE}" \
      --modules "${MODULES}" \
      --model "${MODEL}" \
      --log-events
  else
    run "${PYTHON_BIN}" -m backend.manual_cli enhance \
      --project-root "${PROJECT_ROOT}" \
      --top-module "${TOP_MODULE}" \
      --all-modules \
      --module-filter "${MODULE_FILTER}" \
      --model "${MODEL}" \
      --log-events
  fi
fi

if [[ "${SKIP_COMPOSE}" -eq 0 ]]; then
  run "${PYTHON_BIN}" -m backend.manual_cli compose \
    --project-root "${PROJECT_ROOT}" \
    --top-module "${TOP_MODULE}" \
    --model "${REVIEW_MODEL}" \
    --log-events
else
  echo "Skip compose: --skip-compose is set."
fi

run "${PYTHON_BIN}" -m backend.manual_cli status \
  --project-root "${PROJECT_ROOT}" \
  --top-module "${TOP_MODULE}" \
  --log-events
