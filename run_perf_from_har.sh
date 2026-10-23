#!/usr/bin/env bash
# HAR → k6/JMeter 压测一键流水线（Linux 版，对标 run_perf_from_har.ps1）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

HAR=""
ENGINE="k6"
SMOKE=""
SKIP_RUN=false
AUTH_PROFILE="templates/auth_profiles/generic_rest.yaml"

usage() {
  echo "用法: ./run_perf_from_har.sh -Har capture.har [-Engine k6|jmeter|both] [-Smoke] [-SkipRun]"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Har|--har) HAR="$2"; shift 2 ;;
    -Engine|--engine) ENGINE="$2"; shift 2 ;;
    -Smoke|--smoke) SMOKE="--smoke"; shift ;;
    -SkipRun|--skip-run) SKIP_RUN=true; shift ;;
    -AuthProfile|--auth-profile) AUTH_PROFILE="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "未知参数: $1"; usage 1 ;;
  esac
done

[[ -n "$HAR" ]] || usage 1
[[ -f "$HAR" ]] || { echo "HAR 不存在: $HAR"; exit 1; }

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[[ -n "${PYTHON:-}" ]] || { echo "未找到 python3"; exit 1; }

K6_SPEC="templates/har_perf_k6.md"
JM_SPEC="templates/har_perf_jmeter.md"

echo "== Step 1: HAR -> perf spec =="
if [[ "$ENGINE" == "both" || "$ENGINE" == "k6" ]]; then
  "$PYTHON" codegen/har_to_perf.py -i "$HAR" -o "$K6_SPEC" --engine k6 $SMOKE
fi
if [[ "$ENGINE" == "both" || "$ENGINE" == "jmeter" ]]; then
  "$PYTHON" codegen/har_to_perf.py -i "$HAR" -o "$JM_SPEC" --engine jmeter $SMOKE
fi

echo "== Step 2: spec -> 脚本 =="
if [[ "$ENGINE" == "both" || "$ENGINE" == "k6" ]]; then
  "$PYTHON" codegen/run_spec.py "$K6_SPEC" -o output/har_perf_k6.js
fi
if [[ "$ENGINE" == "both" || "$ENGINE" == "jmeter" ]]; then
  "$PYTHON" codegen/run_spec.py "$JM_SPEC" -o output/har_perf_jmeter.jmx
fi

echo "== Step 3: Token =="
"$PYTHON" codegen/fetch_perf_token.py --auth-profile "$AUTH_PROFILE" --output-env output/.perf_env
if [[ -f output/.perf_env ]]; then
  set -a
  # shellcheck disable=SC1091
  source output/.perf_env
  set +a
fi

if $SKIP_RUN; then
  echo "已生成脚本（SkipRun），Token 已写入 output/.perf_env"
  exit 0
fi

EXIT=0
if [[ "$ENGINE" == "both" || "$ENGINE" == "k6" ]] && [[ -f output/har_perf_k6.js ]]; then
  if command -v k6 >/dev/null 2>&1; then
    echo "== Step 4: k6 =="
    k6 run \
      -e "BASE_URL=${TEST_BASE_URL:-http://your-server:5001}" \
      -e "PERF_ACCESS_TOKEN=${PERF_ACCESS_TOKEN:-}" \
      -e "PERF_TENANT_ID=${PERF_TENANT_ID:-}" \
      output/har_perf_k6.js || EXIT=$?
  else
    echo "跳过 k6 执行（未安装 k6）"
  fi
fi

if [[ "$ENGINE" == "both" || "$ENGINE" == "jmeter" ]] && [[ -f output/har_perf_jmeter.jmx ]]; then
  if command -v jmeter >/dev/null 2>&1; then
    echo "== Step 4: JMeter =="
    jmeter -n -t output/har_perf_jmeter.jmx -l output/har_result.jtl -j output/jmeter.log || EXIT=$?
  else
    echo "跳过 JMeter 执行（未安装 jmeter）"
  fi
fi

exit "$EXIT"
