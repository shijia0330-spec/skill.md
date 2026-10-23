#!/usr/bin/env bash
# 对外交付 zip：排除 output/、缓存与本地日志（与 .gitignore 一致）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STAMP="$(date +%Y%m%d)"
OUT_ZIP="${ROOT}/skills-V3.1-external-${STAMP}.zip"

echo "验收中..."
(cd "$SCRIPT_DIR" && ./verify_all.sh)

echo "打包: $OUT_ZIP"
(
  cd "$ROOT"
  zip -r "$OUT_ZIP" \
    skills-专业版V3.1 \
    skills3.1使用手册 \
    -x 'skills-专业版V3.1/output/*' \
    -x 'skills-专业版V3.1/**/__pycache__/*' \
    -x 'skills-专业版V3.1/**/.pytest_cache/*' \
    -x 'skills-专业版V3.1/.heal_cache/*' \
    -x 'skills-专业版V3.1/jmeter.log' \
    -x 'skills-专业版V3.1/.env' \
    -x 'skills-专业版V3.1/.env.*'
)

echo "完成: $OUT_ZIP"
ls -lh "$OUT_ZIP"