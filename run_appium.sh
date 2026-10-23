#!/usr/bin/env bash
# Appium pytest 入口：健康检查 + adb 设备 + 环境变量 + pytest
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PYTHONPATH="${ROOT}/codegen${PYTHONPATH:+:$PYTHONPATH}"
export APPIUM_ARTIFACTS_DIR="${APPIUM_ARTIFACTS_DIR:-output/appium_artifacts}"
export DEFECT_DRAFTS="${DEFECT_DRAFTS:-1}"
export DEFECT_DRAFT_DIR="${DEFECT_DRAFT_DIR:-output/bugs}"
export PROGRESS_REPORT="${PROGRESS_REPORT:-1}"
export PROGRESS_REPORT_DIR="${PROGRESS_REPORT_DIR:-output/reports}"

# 加载 .env.appium（若存在）
if [[ -f .env.appium ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.appium
  set +a
  echo "[run_appium] loaded .env.appium"
fi

APPIUM_URL="${APPIUM_SERVER_URL:-http://127.0.0.1:4723}"
echo "[run_appium] APPIUM_SERVER_URL=$APPIUM_URL"
echo "[run_appium] TEST_BASE_URL=${TEST_BASE_URL:-（未设，使用 spec base_url）}"
echo "[run_appium] APPIUM_ARTIFACTS_DIR=$APPIUM_ARTIFACTS_DIR"

mkdir -p "$APPIUM_ARTIFACTS_DIR"

# Appium 健康检查
if command -v curl >/dev/null 2>&1; then
  if curl -sf "${APPIUM_URL%/}/status" >/dev/null 2>&1; then
    echo "[run_appium] Appium status: OK"
  else
    echo "[run_appium] WARN: Appium 未响应 ${APPIUM_URL}/status — 请先 appium &" >&2
  fi
fi

# adb 设备
if command -v adb >/dev/null 2>&1; then
  echo "[run_appium] adb devices:"
  adb devices -l | head -20
  if [[ -n "${ANDROID_UDID:-}" ]]; then
    count="$(adb devices | grep -c "^${ANDROID_UDID}[[:space:]]" || true)"
    if [[ "$count" -lt 1 ]]; then
      echo "[run_appium] WARN: ANDROID_UDID=$ANDROID_UDID 未在 adb devices 中" >&2
    fi
  fi
else
  echo "[run_appium] WARN: adb 未安装，跳过设备检查" >&2
fi

TARGET="${1:-output/appium_e2e.py}"
shift || true

if [[ ! -f "$TARGET" ]]; then
  echo "[run_appium] 找不到脚本: $TARGET" >&2
  echo "用法: ./run_appium.sh [output/xxx.py] [pytest args...]" >&2
  exit 1
fi

echo "[run_appium] pytest $TARGET $*"
python3 -m pytest "$TARGET" -v --tb=short "$@"
