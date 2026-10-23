#!/usr/bin/env bash
# skills 专业版 V3.0 — 一键验收（14 步）
# 用法:
#   ./verify_all.sh              # 无后端：codegen + 引擎 + collect-only
#   ./verify_all.sh --with-api   # 有 seckill_finance_system 时跑 API 冒烟
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

WITH_API=false
for arg in "$@"; do
  case "$arg" in
    --with-api) WITH_API=true ;;
    -h|--help)
      echo "用法: ./verify_all.sh [--with-api]"
      echo "  --with-api  需要 seckill_finance_system；读取 TEST_BASE_URL（默认 http://your-server:5001）"
      exit 0
      ;;
  esac
done

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
if [[ -z "${PYTHON:-}" ]]; then
  echo "[FAIL] 未找到 python3"
  exit 1
fi

PASS=0
FAIL=0
SKIP=0

ok()   { echo "[OK] $1"; PASS=$((PASS + 1)); }
bad()  { echo "[FAIL] $1"; FAIL=$((FAIL + 1)); }
skip() { echo "⏭  $1"; SKIP=$((SKIP + 1)); }

echo "=========================================="
echo " skills V3.0 一键验收"
echo " 根目录: $SCRIPT_DIR"
echo "=========================================="
echo ""

# 1. 依赖
echo "--- [1/14] Python 依赖 ---"
if $PYTHON -c "import yaml, pytest, requests" 2>/dev/null; then
  ok "PyYAML + pytest + requests"
else
  bad "缺少依赖: pip install PyYAML pytest requests"
fi
echo ""

# 2. codegen selftest
echo "--- [2/14] codegen 自测 ---"
if $PYTHON codegen/selftest_bundle.py >/tmp/skills_selftest.log 2>&1; then
  ok "codegen/selftest_bundle.py"
else
  bad "codegen/selftest_bundle.py"
  tail -8 /tmp/skills_selftest.log || true
fi
echo ""

# 3. RAG
echo "--- [3/14] RAG 引擎 ---"
if (cd rag-engine/scripts && $PYTHON service.py >/tmp/skills_rag.log 2>&1); then
  ok "rag-engine service.py"
else
  bad "rag-engine service.py"
  tail -5 /tmp/skills_rag.log || true
fi
if $PYTHON testcase-skills/生成/scripts/rag_prefetch.py --query "登录模块测试" --top-k 3 >/tmp/skills_rag_prefetch.log 2>&1; then
  ok "testcase-skills/生成/scripts/rag_prefetch.py"
else
  bad "testcase-skills/生成/scripts/rag_prefetch.py"
  tail -5 /tmp/skills_rag_prefetch.log || true
fi
echo ""

# 4. CI 门禁
echo "--- [4/14] CI 门禁 ---"
if (cd ci-gate/scripts && $PYTHON ci_gate.py --env prod >/tmp/skills_ci.log 2>&1); then
  ok "ci-gate prod"
else
  bad "ci-gate prod"
  tail -5 /tmp/skills_ci.log || true
fi
echo ""

# 5. defect-sync dry-run
echo "--- [5/14] 缺陷同步 dry-run ---"
mkdir -p output/bugs
if [[ ! -f output/bugs/BUG-verify-sample.md ]]; then
  cat > output/bugs/BUG-verify-sample.md << 'EOF'
# 缺陷报告草稿 — BUG-VERIFY-001
| 字段 | 值 |
|------|-----|
| 缺陷编号 | BUG-VERIFY-001 |
| 标题 | verify_all 样例 |
| 严重程度 | Low |
| 缺陷类型 | 功能 |
| 当前状态 | Draft |
| 优先级 | P3 |
| 分流 | 产品缺陷（待人工确认） |
- pytest nodeid：`verify.py::test_sample`
## 问题描述
verify_all dry-run 样例
EOF
fi
if (cd defect-sync/scripts && $PYTHON defect_sync.py push ../../output/bugs/BUG-verify-sample.md --platform custom --dry-run --confirm >/tmp/skills_sync.log 2>&1); then
  ok "defect-sync dry-run"
else
  bad "defect-sync dry-run"
  tail -5 /tmp/skills_sync.log || true
fi
if (cd defect-sync/scripts && $PYTHON defect_sync.py push ../../output/bugs/ --platform custom --dry-run --confirm 2>&1 | tee /tmp/skills_sync_batch.log | tail -3); then
  if grep -q "本批重复指纹" /tmp/skills_sync_batch.log; then
    ok "defect-sync 同批指纹去重"
  else
    skip "defect-sync 同批指纹去重（bugs/ 无重复指纹草稿）"
  fi
else
  bad "defect-sync 同批 push dry-run"
fi
echo ""

# 6. failure-analyzer
echo "--- [6/14] 失败分析 ---"
if $PYTHON defect-analysis/failure_analyzer.py >/tmp/skills_failure_analysis.log 2>&1; then
  ok "defect-analysis/failure_analyzer.py"
else
  bad "defect-analysis/failure_analyzer.py"
  tail -5 /tmp/skills_failure_analysis.log || true
fi
echo ""

# 7. step6 用例质量门禁
echo "--- [7/14] Step6 用例自检 ---"
STEP6_RC=0
$PYTHON testcase-skills/生成/scripts/step6_validator.py examples/output_seckill_auth_testcases.md >/tmp/skills_step6.log 2>&1 || STEP6_RC=$?
if [[ "$STEP6_RC" -eq 0 ]]; then
  ok "step6_validator 黄金样例通过"
elif [[ "$STEP6_RC" -eq 3 ]]; then
  ok "step6_validator 仅 P2（可接受）"
elif [[ "$STEP6_RC" -eq 2 ]]; then
  bad "step6_validator 有 P1 建议"
  tail -8 /tmp/skills_step6.log || true
else
  bad "step6_validator 有 P0 阻塞"
  tail -8 /tmp/skills_step6.log || true
fi
echo ""

# 8. generate + pytest (API)
echo "--- [8/14] API 生成与 pytest collect ---"
chmod +x generate.sh run_pytest.sh run_pytest_ui.sh run_perf_from_har.sh generate_jmeter.sh run_jmeter.sh 2>/dev/null || true
if ./generate.sh templates/api_smoke.md >/tmp/skills_gen.log 2>&1; then
  ok "generate.sh api_smoke.md"
else
  bad "generate.sh api_smoke.md"
fi

if ./run_pytest.sh output/api_smoke.py --collect-only -q 2>&1 | tee /tmp/skills_collect.log | tail -2; then
  if grep -qE "[0-9]+ tests collected" /tmp/skills_collect.log; then
    ok "pytest collect-only ($(grep -oE '[0-9]+ tests collected' /tmp/skills_collect.log | head -1))"
  else
    bad "pytest collect-only 未看到 tests collected"
  fi
else
  bad "pytest collect-only"
fi

echo ""
echo "--- [9/14] UI 生成与 pytest collect ---"
if ./generate.sh templates/ui_smoke_one_page.md >/tmp/skills_gen_ui.log 2>&1; then
  ok "generate.sh ui_smoke_one_page.md"
else
  bad "generate.sh ui_smoke_one_page.md"
  tail -5 /tmp/skills_gen_ui.log || true
fi
unset PYTEST_DISABLE_PLUGIN_AUTOLOAD
export PYTHONPATH="${SCRIPT_DIR}/codegen${PYTHONPATH:+:$PYTHONPATH}"
if ./run_pytest_ui.sh output/ui_smoke_one_page.py --collect-only -q 2>&1 | tee /tmp/skills_collect_ui.log | tail -2; then
  if grep -qE "[0-9]+ tests? collected" /tmp/skills_collect_ui.log; then
    ok "UI pytest collect-only ($(grep -oE '[0-9]+ tests? collected' /tmp/skills_collect_ui.log | head -1))"
  elif grep -qE "No module named|ModuleNotFoundError" /tmp/skills_collect_ui.log; then
    skip "UI collect-only（缺 playwright 等依赖，codegen 已通过）"
  else
    bad "UI pytest collect-only 未看到 tests collected"
  fi
else
  if grep -qE "No module named|ModuleNotFoundError" /tmp/skills_collect_ui.log; then
    skip "UI collect-only（缺 playwright 等依赖，codegen 已通过）"
  else
    bad "UI pytest collect-only"
  fi
fi

echo ""
echo "--- [10/14] Appium 生成与编译 ---"
if ./generate.sh templates/appium_e2e.md >/tmp/skills_gen_appium.log 2>&1; then
  ok "generate.sh appium_e2e.md"
else
  bad "generate.sh appium_e2e.md"
  tail -5 /tmp/skills_gen_appium.log || true
fi
if [[ -f output/appium_e2e.py ]]; then
  if $PYTHON -m py_compile output/appium_e2e.py 2>/tmp/skills_appium_compile.log; then
    ok "appium_e2e.py py_compile"
  else
    bad "appium_e2e.py py_compile"
    cat /tmp/skills_appium_compile.log || true
  fi
  if grep -q "RAG context" output/appium_e2e.py 2>/dev/null; then
    ok "Appium 生成物含 RAG 注释块"
  else
    skip "Appium RAG 注释（索引不可用或未命中时跳过）"
  fi
  UI_AUTO="$SCRIPT_DIR/output/_pipeline/seckill_ui_cases_ui_automation.json"
  if [[ -f "$UI_AUTO" ]]; then
    if $PYTHON codegen/testcase_to_appium_spec.py -i "$UI_AUTO" -o /tmp/verify_appium_spec.md \
        --app-package com.verify.demo --app-activity .Main >/tmp/skills_appium_spec.log 2>&1; then
      ok "testcase_to_appium_spec.py 规则映射"
    else
      bad "testcase_to_appium_spec.py"
      tail -5 /tmp/skills_appium_spec.log || true
    fi
  else
    skip "testcase_to_appium_spec（无 seckill_ui_cases_ui_automation.json）"
  fi
else
  bad "output/appium_e2e.py 未生成"
fi

echo ""
echo "--- [11/14] k6 codegen ---"
if ./generate.sh templates/perf_test_k6.md >/tmp/skills_gen_k6.log 2>&1; then
  ok "generate.sh perf_test_k6.md"
  if [[ -f output/perf_test_k6.js ]] && grep -q "k6/http" output/perf_test_k6.js; then
    ok "perf_test_k6.js 含 k6/http"
  else
    bad "perf_test_k6.js 无效"
  fi
else
  bad "generate.sh perf_test_k6.md"
  tail -5 /tmp/skills_gen_k6.log || true
fi

echo ""
echo "--- [12/14] JMeter 生成与冒烟 ---"
if command -v jmeter >/dev/null 2>&1; then
  if ./generate_jmeter.sh >/tmp/skills_jmeter_gen.log 2>&1; then
    ok "generate_jmeter.sh"
  else
    bad "generate_jmeter.sh"
    tail -5 /tmp/skills_jmeter_gen.log || true
  fi
  if [[ -f output/seckill_load.jmx ]]; then
    BASE_URL="${TEST_BASE_URL:-http://your-server:5001}"
    if curl -sf "${BASE_URL}/" >/dev/null 2>&1; then
      if THREADS=2 DURATION=5 RAMP_TIME=1 TEST_BASE_URL="$BASE_URL" \
        ./run_jmeter.sh 2>&1 | tee /tmp/skills_jmeter_run.log | tail -3; then
        if grep -q "Err:     0 (0.00%)" /tmp/skills_jmeter_run.log; then
          ok "run_jmeter.sh 冒烟 Err=0"
        else
          bad "run_jmeter.sh 有错误请求"
        fi
      else
        bad "run_jmeter.sh"
      fi
    else
      skip "后端不可达 $BASE_URL，跳过 JMeter 冒烟"
    fi
  else
    bad "output/seckill_load.jmx 未生成"
  fi
else
  skip "未安装 jmeter，跳过 JMeter 验收"
fi

echo ""
echo "--- [13/14] intent-router 话术回归 ---"
if $PYTHON codegen/test_intent_router_mapping.py >/tmp/skills_intent.log 2>&1; then
  ok "test_intent_router_mapping.py"
else
  bad "test_intent_router_mapping.py"
  tail -8 /tmp/skills_intent.log || true
fi

echo ""
echo "--- [14/14] conftest 进度/缺陷钩子 ---"
HOOK_TEST="codegen/examples/hook_verify_fail.py"
MARKER="hook_verify_intentional_fail"
BEFORE_BUGS="$(find output/bugs -name 'BUG-*.md' 2>/dev/null | wc -l)"
set +e
./run_pytest.sh "$HOOK_TEST" -q --tb=no -k "$MARKER" >/tmp/skills_hook.log 2>&1
HOOK_RC=$?
set -e
if [[ "$HOOK_RC" -ne 0 ]]; then
  ok "hook 故意失败 pytest 退出非 0"
else
  bad "hook 故意失败 pytest 应失败"
fi
if [[ -f output/reports/progress.json ]] && grep -q '"failed"' output/reports/progress.json; then
  ok "progress.json 含 failed 统计"
else
  bad "progress.json 未更新失败统计"
fi
AFTER_BUGS="$(find output/bugs -name 'BUG-*.md' 2>/dev/null | wc -l)"
if grep -rq "$MARKER" output/bugs/ 2>/dev/null || [[ "$AFTER_BUGS" -gt "$BEFORE_BUGS" ]]; then
  ok "缺陷草稿钩子已写入 output/bugs/"
else
  bad "缺陷草稿钩子未触发"
fi

if [[ "$WITH_API" == true ]]; then
  echo ""
  echo "--- [可选] API 联调 ---"
  export TEST_BASE_URL="${TEST_BASE_URL:-http://your-server:5001}"
  export TEST_USERNAME="${TEST_USERNAME:-admin}"
  export TEST_PASSWORD="${TEST_PASSWORD:-admin123}"
  echo "TEST_BASE_URL=$TEST_BASE_URL"

  if curl -sf "${TEST_BASE_URL}/" >/dev/null 2>&1; then
    ok "后端可达 $TEST_BASE_URL"
    # 生成的 pytest 已含 setup: test_init（session autouse），无需再手动 curl init

    for tpl in api_smoke seckill_api_smoke api_auth seckill_api_auth api_health api_scenario_register seckill_query_tests api_db_check; do
      ./generate.sh "templates/${tpl}.md" >/dev/null 2>&1 || { bad "generate $tpl"; continue; }
      if ./run_pytest.sh "output/${tpl}.py" -q --tb=no 2>&1 | tee "/tmp/skills_${tpl}.log" | tail -1; then
        ok "pytest $tpl"
      else
        bad "pytest $tpl（见 /tmp/skills_${tpl}.log）"
      fi
    done
  else
    skip "后端不可达 $TEST_BASE_URL，跳过 API 联调"
  fi
fi

echo ""
echo "=========================================="
echo " 通过: $PASS   失败: $FAIL   跳过: $SKIP"
echo "=========================================="
[[ "$FAIL" -eq 0 ]]
