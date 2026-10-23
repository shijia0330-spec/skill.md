#!/usr/bin/env bash
# UI 登录演示 — 抖音录制用，一条命令跑完全流程（有头浏览器）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export TEST_BASE_URL="${TEST_BASE_URL:-http://your-server:5173}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"

echo "========== 1/5 generate.sh =========="
./generate.sh templates/ui_login.md

echo ""
echo "========== 2/5 locator_healer.py =========="
python3 UI-skills/执行/scripts/locator_healer.py

echo ""
echo "========== 3/5 检查前端 =========="
if curl -sf "${TEST_BASE_URL%/}/login" -o /dev/null; then
  echo "前端 OK: ${TEST_BASE_URL}"
else
  echo "错误: 前端不可达 ${TEST_BASE_URL}/login"
  echo "请先启动 seckill_finance_system（Docker: 5173 端口）"
  exit 1
fi

echo ""
echo "========== 4/5 pytest --headed =========="
cd output
if [[ -z "${DISPLAY:-}" ]] && command -v xvfb-run >/dev/null 2>&1; then
  echo "(无 DISPLAY，使用 xvfb-run 有头模式)"
  xvfb-run -a --server-args='-screen 0 1280x720x24' python3 -m pytest ui_login.py -v --headed
else
  echo "(DISPLAY=${DISPLAY:-未设置}，直接有头模式)"
  python3 -m pytest ui_login.py -v --headed
fi

echo ""
echo "========== 5/5 collect-only =========="
python3 -m pytest ui_login.py --collect-only -q

echo ""
echo "========== 全部完成 =========="
