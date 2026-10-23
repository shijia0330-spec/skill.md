#!/usr/bin/env bash
# JMeter 压测执行（需先 ./generate_jmeter.sh）
# 用法:
#   ./run_jmeter.sh                          # 默认冒烟: 2 线程, 10 秒
#   ./run_jmeter.sh --full                   # 正式压测: 10 线程, 60 秒
#   THREADS=50 DURATION=300 ./run_jmeter.sh  # 自定义并发
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

JMX="${JMETER_SCRIPT:-output/seckill_load.jmx}"
MODE="smoke"

for arg in "$@"; do
  case "$arg" in
    --full) MODE="full" ;;
    -h|--help)
      echo "用法: ./run_jmeter.sh [--full]"
      echo "  --full   10 线程 / 60 秒（默认冒烟 2 线程 / 10 秒）"
      echo ""
      echo "环境变量:"
      echo "  TEST_BASE_URL   默认 http://your-server:5001"
      echo "  TEST_USERNAME   默认 admin"
      echo "  TEST_PASSWORD   默认 admin123"
      echo "  THREADS RAMP_TIME DURATION  覆盖并发参数"
      echo "  JMETER_SCRIPT   默认 output/seckill_load.jmx"
      exit 0
      ;;
  esac
done

if [[ ! -f "$JMX" ]]; then
  echo "未找到 $JMX，先执行 ./generate_jmeter.sh"
  exit 1
fi

if ! command -v jmeter >/dev/null 2>&1; then
  echo "[FAIL] 未找到 jmeter，请先安装 Apache JMeter 5.x"
  exit 1
fi

BASE_URL="${TEST_BASE_URL:-http://your-server:5001}"
USERNAME="${TEST_USERNAME:-admin}"
PASSWORD="${TEST_PASSWORD:-admin123}"

# 从 TEST_BASE_URL 解析 HOST / PORT
read -r HOST PORT <<< "$(python3 -c "
from urllib.parse import urlparse
u = urlparse('${BASE_URL}')
host = u.hostname or '127.0.0.1'
port = u.port or (443 if u.scheme == 'https' else 80)
print(host, port)
")"

if [[ "$MODE" == "full" ]]; then
  THREADS="${THREADS:-10}"
  DURATION="${DURATION:-60}"
  RAMP_TIME="${RAMP_TIME:-10}"
else
  THREADS="${THREADS:-2}"
  DURATION="${DURATION:-10}"
  RAMP_TIME="${RAMP_TIME:-1}"
fi

HEALTH_PATH="${HEALTH_PATH:-/}"
RESULTS="${JMETER_RESULTS:-output/jmeter-results.jtl}"
REPORT_DIR="${JMETER_REPORT:-output/jmeter-report}"

mkdir -p output
rm -f "$RESULTS"
rm -rf "$REPORT_DIR"

echo "========== JMeter 压测 =========="
echo "脚本:   $JMX"
echo "目标:   http://${HOST}:${PORT}"
echo "并发:   ${THREADS} 线程, 爬坡 ${RAMP_TIME}s, 持续 ${DURATION}s"
echo "结果:   $RESULTS"
echo "报告:   $REPORT_DIR/"
echo "================================="

jmeter -n -t "$JMX" \
  -JHOST="$HOST" \
  -JPORT="$PORT" \
  -JUSERNAME="$USERNAME" \
  -JPASSWORD="$PASSWORD" \
  -JHEALTH_PATH="$HEALTH_PATH" \
  -JTHREADS="$THREADS" \
  -JDURATION="$DURATION" \
  -JRAMP_TIME="$RAMP_TIME" \
  -l "$RESULTS" \
  -e -o "$REPORT_DIR"

echo ""
echo "[OK] 压测完成"
echo "   HTML 报告: $REPORT_DIR/index.html"
echo "   原始数据:  $RESULTS"
