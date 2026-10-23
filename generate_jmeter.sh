#!/usr/bin/env bash
# JMeter 压测脚本一键生成（对齐 seckill_finance_system）
# 用法:
#   ./generate_jmeter.sh                    # → output/seckill_load.jmx
#   ./generate_jmeter.sh output/custom.jmx  # 指定输出路径
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/load-testing/references/seckill_load.jmx"
OUT="${1:-$SCRIPT_DIR/output/seckill_load.jmx}"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "[FAIL] 找不到模板: $TEMPLATE"
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
cp "$TEMPLATE" "$OUT"

echo "[OK] 已生成 JMeter 脚本: $OUT"
echo ""
echo "运行压测:"
echo "  ./run_jmeter.sh"
echo ""
echo "或手动指定参数:"
echo "  TEST_BASE_URL=http://your-server:5001 \\"
echo "  THREADS=10 DURATION=60 RAMP_TIME=10 \\"
echo "  ./run_jmeter.sh"
echo ""
echo "说明:"
echo "  - 模板与 load-testing/references/k6-template.js 接口对齐"
echo "  - 场景: 健康检查 → 登录(提取token) → 商品列表 → Profile"
echo "  - JMX 内 Asserion.test_strings 为 JMeter 官方历史属性名（非拼写错误）"
