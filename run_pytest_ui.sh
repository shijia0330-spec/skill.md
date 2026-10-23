#!/usr/bin/env bash
# UI pytest 入口：trace + 失败截图 + 缺陷草稿 + 进度报告（对标 run_pytest_ui.ps1）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export DEFECT_DRAFTS="${DEFECT_DRAFTS:-1}"
export DEFECT_DRAFT_DIR="${DEFECT_DRAFT_DIR:-output/bugs}"
export UI_ARTIFACTS_DIR="${UI_ARTIFACTS_DIR:-output/ui_artifacts}"
export PROGRESS_REPORT="${PROGRESS_REPORT:-1}"
export PROGRESS_REPORT_DIR="${PROGRESS_REPORT_DIR:-output/reports}"
export FAILURE_ANALYSIS="${FAILURE_ANALYSIS:-1}"
export FAILURE_ANALYSIS_DIR="${FAILURE_ANALYSIS_DIR:-output/reports}"
export PYTHONPATH="$SCRIPT_DIR/codegen${PYTHONPATH:+:$PYTHONPATH}"

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
if [[ -z "${PYTHON:-}" ]]; then
  echo "未找到 python3"
  exit 1
fi

mkdir -p "$UI_ARTIFACTS_DIR" "$DEFECT_DRAFT_DIR" "$PROGRESS_REPORT_DIR"

COLLECT_ONLY=false
for arg in "$@"; do
  [[ "$arg" == "--collect-only" || "$arg" == --collect-only=* ]] && COLLECT_ONLY=true
done

USE_ALLURE=true
if [[ "${ALLURE:-}" =~ ^(0|false|no|off)$ ]]; then USE_ALLURE=false; fi
if $COLLECT_ONLY; then USE_ALLURE=false; fi

DEFAULTS=(
  "--tracing=retain-on-failure"
  "--screenshot=only-on-failure"
  "--output" "$UI_ARTIFACTS_DIR/playwright-output"
)

ALLURE_ARGS=()
if $USE_ALLURE; then
  export ALLURE_RESULTS_DIR="${ALLURE_RESULTS_DIR:-output/allure-results-ui}"
  export ALLURE_HTML_DIR="${ALLURE_HTML_DIR:-output/allure-report-ui}"
  mkdir -p "$ALLURE_RESULTS_DIR"
  ALLURE_ARGS=(--alluredir="$ALLURE_RESULTS_DIR" --clean-alluredir)
  echo "[run_pytest_ui] ALLURE=1 → $ALLURE_RESULTS_DIR"
fi

echo "[run_pytest_ui] UI_ARTIFACTS_DIR=$UI_ARTIFACTS_DIR"
echo "[run_pytest_ui] DEFECT_DRAFT_DIR=$DEFECT_DRAFT_DIR"
echo ""

if [[ "${UI_PRETEST:-}" == "1" ]]; then
  BASE="${TEST_BASE_URL:-http://your-server:5001}"
  "$PYTHON" -c "import sys; sys.path.insert(0, 'codegen'); from ui_lib.pretest import assert_readiness; assert_readiness('${BASE}')"
fi

set +e
"$PYTHON" -m pytest "${DEFAULTS[@]}" "${ALLURE_ARGS[@]}" "$@"
EXIT=$?
set -e

if $USE_ALLURE && command -v allure >/dev/null 2>&1; then
  HTML_DIR="${ALLURE_HTML_DIR:-output/allure-report-ui}"
  allure generate "$ALLURE_RESULTS_DIR" -o "$HTML_DIR" --clean 2>/dev/null || true
  if [[ -f "$HTML_DIR/index.html" ]]; then
    echo ""
    echo "UI Allure report: $SCRIPT_DIR/$HTML_DIR/index.html"
  fi
elif $USE_ALLURE; then
  echo "提示: 安装 allure 后可生成 HTML 报告，或使用 scripts/allure_serve.py"
fi

if [[ $EXIT -ne 0 ]]; then
  echo ""
  echo "Artifacts: $SCRIPT_DIR/$UI_ARTIFACTS_DIR"
  [[ -d "$DEFECT_DRAFT_DIR" ]] && echo "Defect drafts: $SCRIPT_DIR/$DEFECT_DRAFT_DIR"
fi
exit "$EXIT"
