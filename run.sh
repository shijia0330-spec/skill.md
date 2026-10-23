#!/bin/bash
# run.sh — pytest 快捷入口（等价于 run_pytest.sh）
# 用法: ./run.sh output/api_smoke.py -v
# 等价于: ./run_pytest.sh output/api_smoke.py -v
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/run_pytest.sh" "$@"
