#!/usr/bin/env bash
# 在引擎根运行 pytest；会话结束自动写进度报告 + 失败缺陷草稿（conftest.py）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export PROGRESS_REPORT="${PROGRESS_REPORT:-1}"
export PROGRESS_REPORT_DIR="${PROGRESS_REPORT_DIR:-output/reports}"
export DEFECT_DRAFTS="${DEFECT_DRAFTS:-1}"
export DEFECT_DRAFT_DIR="${DEFECT_DRAFT_DIR:-output/bugs}"
export PYTHONPATH="$SCRIPT_DIR/codegen${PYTHONPATH:+:$PYTHONPATH}"

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
if [[ -z "${PYTHON:-}" ]]; then
  echo "未找到 python3"
  exit 1
fi

echo "[run_pytest] PROGRESS_REPORT_DIR=$PROGRESS_REPORT_DIR"
echo "[run_pytest] DEFECT_DRAFT_DIR=$DEFECT_DRAFT_DIR"
echo ""

# 允许失败以便 sessionfinish 写报告与草稿；用例仍返回非 0
set +e
"$PYTHON" -m pytest "$@"
EXIT=$?
set -e

echo ""
if [[ -d "$SCRIPT_DIR/$PROGRESS_REPORT_DIR" ]] || [[ -d "$PROGRESS_REPORT_DIR" ]]; then
  R="${PROGRESS_REPORT_DIR}"
  [[ -d "$SCRIPT_DIR/$PROGRESS_REPORT_DIR" ]] && R="$SCRIPT_DIR/$PROGRESS_REPORT_DIR"
  echo "进度报告目录: $R"
  [[ -f "$R/progress.md" ]] && echo "  Markdown: $R/progress.md"
  [[ -f "$R/progress.json" ]] && echo "  JSON: $R/progress.json"
fi
if [[ $EXIT -ne 0 ]]; then
  if [[ -d "$SCRIPT_DIR/$DEFECT_DRAFT_DIR" ]] || [[ -d "$DEFECT_DRAFT_DIR" ]]; then
    D="${DEFECT_DRAFT_DIR}"
    [[ -d "$SCRIPT_DIR/$DEFECT_DRAFT_DIR" ]] && D="$SCRIPT_DIR/$DEFECT_DRAFT_DIR"
    echo "缺陷草稿目录: $D"
    [[ -f "$D/bug_list.md" ]] && echo "  汇总: $D/bug_list.md"
  fi
fi
exit "$EXIT"
