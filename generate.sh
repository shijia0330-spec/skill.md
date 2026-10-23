#!/bin/bash
# 一键生成测试脚本
# 用法: ./generate.sh <spec文件> [输出目录] [--report] [--env <环境名>]
# 示例: ./generate.sh templates/api_smoke.md
#       ./generate.sh templates/ui_login.md ./tests/
#       ./generate.sh my_spec.md --report
#       ./generate.sh my_spec.md --env staging
#       ./generate.sh templates/data_factory.md       # 造数脚本
#       ./generate.sh templates/perf_test.md          # 性能测试脚本
#       ./generate.sh templates/appium_e2e.md         # Appium + pytest

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---------- 参数解析 ----------
SPEC_FILE=""
OUT_DIR="$SCRIPT_DIR/output"
REPORT=false
ENV_NAME=""
IMPORT_OPENAPI=""
IMPORT_BASE_URL=""
IMPORT_AUTH_PROFILE=""
IMPORT_SMOKE_ONLY=false
IMPORT_TO_CASES=false

# 解析位置参数和选项
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --import-openapi)
            if [[ -z "$2" || "$2" == --* ]]; then
                echo " --import-openapi 需要一个文件路径或 HTTP URL"
                echo "   示例: ./generate.sh --import-openapi openapi.json -o output/api.md"
                exit 1
            fi
            IMPORT_OPENAPI="$2"
            shift 2
            ;;
        --base-url)
            if [[ -z "$2" || "$2" == --* ]]; then
                echo " --base-url 需要一个 URL（仅与 --import-openapi 一起使用）"
                exit 1
            fi
            IMPORT_BASE_URL="$2"
            shift 2
            ;;
        --auth-profile)
            if [[ -z "$2" || "$2" == --* ]]; then
                echo " --auth-profile 需要 YAML/JSON 路径（与 --import-openapi 合用）"
                exit 1
            fi
            IMPORT_AUTH_PROFILE="$2"
            shift 2
            ;;
        --smoke-only)
            IMPORT_SMOKE_ONLY=true
            shift
            ;;
        --to-cases)
            IMPORT_TO_CASES=true
            shift
            ;;
        --report)
            REPORT=true
            shift
            ;;
        --env)
            if [[ -z "$2" || "$2" == --* ]]; then
                echo " --env 需要一个环境名参数"
                echo "   示例: ./generate.sh my_spec.md --env staging"
                exit 1
            fi
            ENV_NAME="$2"
            shift 2
            ;;
        -o)
            if [[ -z "$2" || "$2" == --* ]]; then
                echo " -o 需要一个输出路径参数"
                exit 1
            fi
            OUT_DIR="$(dirname "$2")"
            OUT_FILE_NAME="$(basename "$2")"
            shift 2
            ;;
        -*)
            echo " 未知选项: $1"
            echo "   运行 ./generate.sh 查看帮助信息"
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# 从位置参数中提取 spec 文件和输出目录
SPEC_FILE="${POSITIONAL_ARGS[0]:-}"
if [[ ${#POSITIONAL_ARGS[@]} -ge 2 ]]; then
    OUT_DIR="${POSITIONAL_ARGS[1]}"
fi

# ---------- OpenAPI 导入：与 README 一致，由 generate.sh 转调 codegen ----------
if [[ -n "$IMPORT_BASE_URL" && -z "$IMPORT_OPENAPI" ]]; then
    echo " --base-url 仅可与 --import-openapi 一起使用"
    exit 1
fi

if [[ -n "$IMPORT_OPENAPI" ]]; then
    if [[ -n "$ENV_NAME" ]]; then
        echo " OpenAPI 导入模式不支持 --env（请用 --base-url 或在生成后的 spec 里改 base_url）"
        exit 1
    fi
    if [[ -n "$OUT_FILE_NAME" ]]; then
        OUT_FILE="$OUT_DIR/$OUT_FILE_NAME"
    elif [[ "$IMPORT_TO_CASES" == true ]]; then
        OUT_FILE="$OUT_DIR/imported_cases.json"
    else
        OUT_FILE="$OUT_DIR/imported_spec.md"
    fi
    mkdir -p "$OUT_DIR"
    if ! command -v python3 > /dev/null 2>&1 && ! command -v python > /dev/null 2>&1; then
        echo " 未找到 python3 或 python"
        exit 1
    fi
    PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
    if ! $PYTHON -c "import yaml" > /dev/null 2>&1; then
        echo " 缺少 PyYAML 依赖: pip install PyYAML"
        exit 1
    fi
    IMPORT_ARGS=(--import-openapi "$IMPORT_OPENAPI" -o "$OUT_FILE")
    if [[ -n "$IMPORT_BASE_URL" ]]; then
        IMPORT_ARGS+=(--base-url "$IMPORT_BASE_URL")
    fi
    if [[ -n "$IMPORT_AUTH_PROFILE" ]]; then
        IMPORT_ARGS+=(--auth-profile "$IMPORT_AUTH_PROFILE")
    fi
    if [[ "$IMPORT_SMOKE_ONLY" == true ]]; then
        IMPORT_ARGS+=(--smoke-only)
    fi
    if [[ "$IMPORT_TO_CASES" == true ]]; then
        IMPORT_ARGS+=(--to-cases)
    fi
    PYTHONUNBUFFERED=1 "$PYTHON" -u "$SCRIPT_DIR/codegen/run_spec.py" "${IMPORT_ARGS[@]}"
    echo ""
    if [[ "$IMPORT_TO_CASES" == true ]]; then
        echo " 已生成 cases 草稿: $OUT_FILE"
        echo "   下一步: 评审后 python codegen/testcase_to_api_spec.py -i \"$OUT_FILE\" -o templates/imported_api.md"
    else
        echo " 已生成 spec: $OUT_FILE"
        echo "   下一步: ./generate.sh \"$OUT_FILE\" [输出目录]  # 由 spec 生成 pytest"
    fi
    exit 0
fi

# ---------- 参数校验 ----------
if [ -z "$SPEC_FILE" ]; then
    cat <<EOF
用法: ./generate.sh <spec文件> [输出目录] [选项]

spec文件: 带 YAML frontmatter 的 .md 文件
输出目录: 生成的 .py 文件存放位置（默认 ./output/）

选项:
    --report              生成脚本后自动运行 pytest 并生成 Allure 报告
    --env <环境名>         从 .env.<环境名> 读取环境变量，替换 spec 中的 \${KEY} 占位符
    --import-openapi <源>  从 OpenAPI/Swagger 生成 spec 或 cases JSON（见 --to-cases）
    --base-url <URL>       与 --import-openapi 合用
    --auth-profile <文件>  鉴权 profile（如 templates/auth_profiles/generic_rest.yaml）
    --smoke-only           冒烟模式（仅 H 主路径，import_mode: smoke）
    --to-cases             输出 cases JSON 草稿而非 spec .md

示例:
    ./generate.sh templates/api_smoke.md
    ./generate.sh templates/ui_login.md ./tests/
    ./generate.sh my_custom_spec.md --report
    ./generate.sh my_custom_spec.md --env staging
    ./generate.sh my_custom_spec.md --env production --report

    内置模板（codegen spec，共 19 个）:
    API 测试（生成 pytest 脚本）:
        templates/api_smoke.md      秒杀财务系统商品：GET/POST /api/products（POST 需管理员 JWT）
        templates/api_auth.md       API 完整测试（含 Bearer Token 登录）
        templates/api_db_check.md   API + 数据库对比验证
        templates/api_scenario_register.md  API 多步场景（注册→profile）

    UI测试（生成 Playwright 脚本）:
        templates/ui_login.md       UI 登录流程
        templates/ui_form.md        UI 表单填写
        templates/ui_e2e.md         UI 端到端流程

    App 移动端（生成 Appium + pytest 脚本）:
        templates/appium_e2e.md     App 端到端（声明式 spec）

    造数（生成 MySQL 插入脚本）:
        templates/data_factory.md   自动生成测试数据

    性能测试（生成 Locust / JMeter 脚本）:
        templates/perf_test.md      HTTP 接口压测（Locust）
        templates/jmeter_test.md    JMeter 压测脚本（OpenAPI 驱动）

    视觉回归（生成 Playwright 截图对比脚本）:
        templates/visual_regression.md  UI 视觉回归测试

    说明 — 以下 5 个为「用例/需求文档」，无 YAML frontmatter，不能 ./generate.sh：
        templates/需求文档.md
        templates/测试用例-需求文档.md
        templates/testcase_generation.md
        templates/testcase_template.md
        templates/testcase_from_bug.md
    完整排除列表见 codegen/excluded_doc_templates.txt（codegen 自测同步读取）

环境变量占位符:
    在 spec 文件中使用 \${KEY} 占位符，配合 --env 选项从 .env 文件读取值:

    # .env.staging
    BASE_URL=http://staging.example.com:8899
    TEST_USERNAME=admin
    TEST_PASSWORD=<你的测试密码>

    # spec 文件中使用
    base_url: \${BASE_URL}
    username: \${TEST_USERNAME}

    # 运行
    ./generate.sh my_spec.md --env staging

快速开始:
    # API 测试（推荐：失败自动写缺陷草稿到 output/bugs/）
    ./generate.sh templates/api_smoke.md
    ./run_pytest.sh output/api_smoke.py -v

    # UI测试（需先安装 Playwright 浏览器）
    ./generate.sh templates/ui_login.md
    cd output && pytest -v

    # 造数（需 pymysql）
    ./generate.sh templates/data_factory.md
    cd output && python data_factory.py

    # 性能测试（需 locust）
    ./generate.sh templates/perf_test.md
    cd output && locust -f perf_test.py --headless -u 10 -r 2 -t 30s

    # 视觉回归（需 playwright）
    ./generate.sh templates/visual_regression.md
    cd output && pytest visual_regression.py --update-snapshots -v  # 首次：生成基线
    cd output && pytest visual_regression.py -v                      # 后续：对比基线

    # App 端到端（需 Appium Server + 设备/模拟器）
    ./generate.sh templates/appium_e2e.md
    cd output && pytest appium_e2e.py -v

    # 生成 Allure 报告
    ./generate.sh templates/api_smoke.md --report

    # OpenAPI → spec（base_url 优先读文档 servers，可用 --base-url 覆盖；路径参数会填示例值）
    ./generate.sh --import-openapi openapi.json -o output/imported.md
    ./generate.sh --import-openapi openapi.json --base-url http://your-server:8080 -o output/imported.md
EOF
    exit 0
fi

# ---------- 检查 spec 文件 ----------
if [ ! -f "$SPEC_FILE" ]; then
    # 尝试在 templates/ 下找
    if [ -f "$SCRIPT_DIR/templates/$SPEC_FILE" ]; then
        SPEC_FILE="$SCRIPT_DIR/templates/$SPEC_FILE"
    else
        echo " 找不到文件: $SPEC_FILE"
        echo "   提示: 运行 ./generate.sh 查看内置模板列表"
        exit 1
    fi
fi

# ---------- --env 选项：解析 .env 文件并替换占位符 ----------
EFFECTIVE_SPEC="$SPEC_FILE"
TEMP_SPEC=""

if [[ -n "$ENV_NAME" ]]; then
    ENV_FILE=""

    # 优先在当前目录查找
    if [ -f "$PWD/.env.${ENV_NAME}" ]; then
        ENV_FILE="$PWD/.env.${ENV_NAME}"
    # 其次在项目根目录（SCRIPT_DIR）查找
    elif [ -f "$SCRIPT_DIR/.env.${ENV_NAME}" ]; then
        ENV_FILE="$SCRIPT_DIR/.env.${ENV_NAME}"
    fi

    if [ -z "$ENV_FILE" ]; then
        echo " 找不到环境文件: .env.${ENV_NAME}"
        echo "   请在当前目录或项目根目录创建该文件"
        echo "   示例: echo 'BASE_URL=http://staging.example.com' > .env.${ENV_NAME}"
        exit 1
    fi

    echo " 加载环境配置: $ENV_FILE"

    # 创建临时 spec 文件（用于替换占位符）
    TEMP_SPEC="$(mktemp /tmp/spec_XXXXXX.md)"
    cp "$SPEC_FILE" "$TEMP_SPEC"
    EFFECTIVE_SPEC="$TEMP_SPEC"

    # 逐行解析 .env 文件，替换占位符
    while IFS= read -r line || [[ -n "$line" ]]; do
        # 跳过空行和注释
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        # 解析 KEY=VALUE（支持引号包裹的值）
        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)[[:space:]]*$ ]]; then
            KEY="${BASH_REMATCH[1]}"
            VALUE="${BASH_REMATCH[2]}"

            # 去除首尾引号
            VALUE="$(echo "$VALUE" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"

            # 用 sed 替换占位符 ${KEY} 为 VALUE
            # 使用 | 作为分隔符避免与 URL 中的 / 冲突
            if [[ "$VALUE" == *"|"* ]]; then
                # 如果值中包含 |，使用不同的分隔符
                ESCAPED_VALUE="$(echo "$VALUE" | sed 's/[&/\]/\\&/g')"
                sed -i "s|\${${KEY}}|${ESCAPED_VALUE}|g" "$TEMP_SPEC"
            else
                sed -i "s|\${${KEY}}|${VALUE}|g" "$TEMP_SPEC"
            fi

            echo "   ✓ ${KEY} = ${VALUE}"
        fi
    done < "$ENV_FILE"

    echo ""
fi

# ---------- 检查依赖 ----------
if ! command -v python3 > /dev/null 2>&1 && ! command -v python > /dev/null 2>&1; then
    echo " 未找到 python3 或 python，请先安装 Python 3.8+"
    exit 1
fi

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)

if ! $PYTHON -c "import yaml" > /dev/null 2>&1; then
    echo " 缺少 PyYAML 依赖"
    echo "   请手动安装: pip install PyYAML"
    echo "   （或: python3 -m pip install PyYAML）"
    exit 1
fi

# ---------- 检测 kind（用于 RAG 预检索 + 运行提示） ----------
SPEC_FM="$(tr -d '\r' < "$EFFECTIVE_SPEC" 2>/dev/null | awk 'BEGIN{c=0} /^---$/{c++; if(c==2)exit; next} c>=1{print}')"
KIND_HINT="$(echo "$SPEC_FM" | grep -E '^kind:' | head -1 | sed 's/kind:[[:space:]]*//' | tr -d '\r')"
PERF_ENGINE=""
if [[ "$KIND_HINT" == "perf_test" ]]; then
    PERF_ENGINE="$(echo "$SPEC_FM" | grep -E '^engine:' | head -1 | sed 's/engine:[[:space:]]*//' | tr -d '\r' | tr 'A-Z' 'a-z')"
    [[ -z "$PERF_ENGINE" ]] && PERF_ENGINE="k6"
fi

# ---------- RAG 预检索（testcase 类 spec 自动生成前检索知识库） ----------
RAG_CONTEXT_FILE=""
if [[ "$KIND_HINT" == "api_pytest" || "$KIND_HINT" == "ui_pytest_playwright" || "$KIND_HINT" == "appium_pytest" ]]; then
    RAG_PREFETCH="$SCRIPT_DIR/testcase-skills/生成/scripts/rag_prefetch.py"
    if [[ -f "$RAG_PREFETCH" ]]; then
        BASENAME_RAG="$(basename "$EFFECTIVE_SPEC" .md)"
        RAG_OUT="$OUT_DIR/rag_context_${BASENAME_RAG}.md"
        echo " RAG 预检索: $SPEC_FILE → $RAG_OUT"
        if PYTHONUNBUFFERED=1 "$PYTHON" -u "$RAG_PREFETCH" "$EFFECTIVE_SPEC" --top-k 5 --out "$RAG_OUT" 2>/dev/null; then
            RAG_CONTEXT_FILE="$RAG_OUT"
            echo "  RAG 上下文已生成"
        else
            echo "  RAG 预检索跳过（无命中或索引不可用，不影响生成）"
        fi
        echo ""
    fi
fi

# ---------- 生成 ----------
if [[ -n "$OUT_FILE_NAME" ]]; then
    # -o 选项指定了完整输出路径
    OUT_FILE="$OUT_DIR/$OUT_FILE_NAME"
else
    BASENAME="$(basename "$EFFECTIVE_SPEC" .md)"
    if [[ "$KIND_HINT" == "jmeter_test" ]]; then
        OUT_FILE="$OUT_DIR/${BASENAME}.jmx"
    elif [[ "$KIND_HINT" == "perf_test" ]]; then
        case "$PERF_ENGINE" in
            k6)     OUT_FILE="$OUT_DIR/${BASENAME}.js" ;;
            jmeter) OUT_FILE="$OUT_DIR/${BASENAME}.jmx" ;;
            *)      OUT_FILE="$OUT_DIR/${BASENAME}.py" ;;
        esac
    else
        OUT_FILE="$OUT_DIR/${BASENAME}.py"
    fi
fi

mkdir -p "$OUT_DIR"

# 将此后所有标准输出同时写入文件，避免部分 IDE / 虚拟机终端吞掉 stdout 时用户看不到提示
exec > >(
  tee "$OUT_DIR/.last_run_message.txt"
)

PYTHONUNBUFFERED=1 "$PYTHON" -u "$SCRIPT_DIR/codegen/run_spec.py" "$EFFECTIVE_SPEC" -o "$OUT_FILE" \
    ${RAG_CONTEXT_FILE:+--rag-context "$RAG_CONTEXT_FILE"}

# 清理临时文件
if [[ -n "$TEMP_SPEC" && -f "$TEMP_SPEC" ]]; then
    rm -f "$TEMP_SPEC"
fi

GEN_OKMSG="[generate.sh] OK -> $OUT_FILE"
printf '%s\n' "$GEN_OKMSG"
printf '%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$OUT_FILE" >"$OUT_DIR/.last_generate_ok" 2>/dev/null || true
echo ""

# ---------- --report 选项：运行 pytest 并生成 Allure 报告 ----------
if [[ "$REPORT" == true ]]; then
    if [[ "$KIND_HINT" == "data_factory" || "$KIND_HINT" == "perf_test" || "$KIND_HINT" == "jmeter_test" ]]; then
        echo "  --report 仅适用于 pytest 产物（api_pytest / ui_pytest_playwright / appium_pytest / visual_regression 等）"
        echo "   当前 kind 为 $KIND_HINT，跳过报告生成。"
    else
        echo " 运行 pytest 并生成 Allure 报告..."
        echo ""

        # 检查 pytest 是否可用
        if ! $PYTHON -m pytest --version > /dev/null 2>&1; then
            echo " 未找到 pytest"
            echo "   请安装: pip install pytest allure-pytest"
            echo ""
            echo "跳过报告生成。"
        else
            # 运行 pytest（引擎根 conftest 会在失败时写缺陷草稿 → output/bugs/）
            export DEFECT_DRAFTS="${DEFECT_DRAFTS:-1}"
            export DEFECT_DRAFT_DIR="${DEFECT_DRAFT_DIR:-$OUT_DIR/bugs}"
            export PYTHONPATH="${SCRIPT_DIR}/codegen${PYTHONPATH:+:$PYTHONPATH}"
            (cd "$SCRIPT_DIR" && $PYTHON -m pytest "$OUT_FILE" -v --alluredir="$OUT_DIR/allure-results") 2>&1 || true

            echo ""
            _BD="$DEFECT_DRAFT_DIR"
            [[ "$_BD" != /* ]] && _BD="$SCRIPT_DIR/$_BD"
            if [[ -d "$_BD" ]]; then
                echo " 失败用例缺陷草稿: $_BD/"
                [[ -f "$_BD/bug_list.md" ]] && echo "   汇总: $_BD/bug_list.md"
                echo ""
            fi

            ALLURE_HTML_DIR="$OUT_DIR/allure-report"
            FALLBACK_HTML="$ALLURE_HTML_DIR/standalone.html"
            _ALLURE_OK=false

            # 优先 allure CLI；不可用或失败时回退 scripts/allure_fallback_report.py
            if command -v allure > /dev/null 2>&1; then
                if allure generate "$OUT_DIR/allure-results" -o "$ALLURE_HTML_DIR" --clean 2>/dev/null; then
                    _ALLURE_OK=true
                    echo " Allure 静态报告: $ALLURE_HTML_DIR/index.html"
                    if [[ "${ALLURE_OPEN_BROWSER:-1}" != "0" ]]; then
                        INDEX_HTML="$ALLURE_HTML_DIR/index.html"
                        if [[ -f "$INDEX_HTML" ]]; then
                            if command -v xdg-open > /dev/null 2>&1; then
                                xdg-open "$INDEX_HTML" 2>/dev/null || true
                            elif command -v open > /dev/null 2>&1; then
                                open "$INDEX_HTML" 2>/dev/null || true
                            elif $PYTHON -c "import webbrowser" 2>/dev/null; then
                                ABS_INDEX="$(cd "$(dirname "$INDEX_HTML")" && pwd)/$(basename "$INDEX_HTML")"
                                $PYTHON -m webbrowser "file://$ABS_INDEX" 2>/dev/null || true
                            fi
                        fi
                    fi
                else
                    echo " allure generate 失败，改用 fallback HTML"
                fi
            fi

            if [[ "$_ALLURE_OK" != true ]] && [[ -d "$OUT_DIR/allure-results" ]]; then
                mkdir -p "$ALLURE_HTML_DIR"
                if $PYTHON "$SCRIPT_DIR/scripts/allure_fallback_report.py" "$OUT_DIR/allure-results" "$FALLBACK_HTML" 2>/dev/null; then
                    echo " Allure 独立报告（fallback）: $FALLBACK_HTML"
                    if [[ "${ALLURE_OPEN_BROWSER:-1}" != "0" ]] && [[ -f "$FALLBACK_HTML" ]]; then
                        if command -v xdg-open > /dev/null 2>&1; then
                            xdg-open "$FALLBACK_HTML" 2>/dev/null || true
                        elif command -v open > /dev/null 2>&1; then
                            open "$FALLBACK_HTML" 2>/dev/null || true
                        elif $PYTHON -c "import webbrowser" 2>/dev/null; then
                            ABS_FB="$(cd "$(dirname "$FALLBACK_HTML")" && pwd)/$(basename "$FALLBACK_HTML")"
                            $PYTHON -m webbrowser "file://$ABS_FB" 2>/dev/null || true
                        fi
                    fi
                else
                    echo " Allure 结果: $OUT_DIR/allure-results"
                    echo " 手动生成: python3 scripts/allure_fallback_report.py $OUT_DIR/allure-results $FALLBACK_HTML"
                fi
            fi

            if [[ "$_ALLURE_OK" == true ]]; then
                echo ""
                echo "交互查看（本地起服务）:"
                echo "    allure serve $OUT_DIR/allure-results"
            fi
        fi

        echo ""
    fi
else
    if [[ "$KIND_HINT" == "data_factory" ]]; then
        echo "运行造数脚本:"
        echo "    cd $OUT_DIR"
        echo "    python ${BASENAME}.py"
        echo ""
        echo "安装依赖:"
        echo "    pip install pymysql"
        echo ""
        echo "设置数据库密码:"
        echo "    export DB_PASSWORD=***"
        echo ""
    elif [[ "$KIND_HINT" == "perf_test" ]]; then
        case "$PERF_ENGINE" in
            k6)
                echo "运行 k6 压测:"
                echo "    export TEST_BASE_URL=http://your-server:5001"
                echo "    k6 run -e TEST_BASE_URL=\$TEST_BASE_URL ${OUT_FILE}"
                echo ""
                echo "需 Bearer Token 时:"
                echo "    python codegen/fetch_perf_token.py --output-env output/.perf_env"
                echo "    k6 run -e PERF_ACCESS_TOKEN=\$PERF_ACCESS_TOKEN ${OUT_FILE}"
                echo ""
                ;;
            jmeter)
                echo "运行 JMeter 压测:"
                echo "    python codegen/run_jmeter_perf.py -t ${OUT_FILE}"
                echo ""
                echo "或手动:"
                echo "    jmeter -n -t ${OUT_FILE} -l output/result.jtl -e -o output/jmeter-report"
                echo ""
                ;;
            *)
                echo "运行 Locust 性能测试:"
                echo "    cd $OUT_DIR"
                echo "    locust -f ${BASENAME}.py --headless -u 10 -r 2 -t 30s"
                echo ""
                echo "安装依赖:"
                echo "    pip install locust"
                echo ""
                echo "或启动 Web UI:"
                echo "    locust -f ${BASENAME}.py"
                echo "    # 浏览器打开 http://your-server:8089"
                echo ""
                ;;
        esac
    elif [[ "$KIND_HINT" == "jmeter_test" ]]; then
        echo "运行 JMeter 压测:"
        echo "    python codegen/run_jmeter_perf.py -t ${OUT_FILE}"
        echo ""
        echo "或:"
        echo "    jmeter -n -t ${OUT_FILE} -l output/result.jtl -e -o output/jmeter-report"
        echo ""
    elif [[ "$KIND_HINT" == "visual_regression" ]]; then
        echo "视觉回归测试:"
        echo "    cd $OUT_DIR"
        echo "    pytest ${BASENAME}.py --update-snapshots -v  # 首次：生成基线截图"
        echo "    pytest ${BASENAME}.py -v                      # 后续：对比基线"
        echo ""
        echo "安装依赖:"
        echo "    pip install pytest-playwright"
        echo "    playwright install chromium"
        echo ""
        echo "更新基线（UI 改版后）:"
        echo "    pytest ${BASENAME}.py --update-snapshots -v"
        echo ""
    elif [[ "$KIND_HINT" == "appium_pytest" ]]; then
        echo "Appium 移动端测试:"
        echo "    cp templates/.env.appium.example .env.appium   # 改 LAN IP"
        echo "    appium &"
        echo "    ./run_appium.sh $OUT_DIR/${BASENAME}.py"
        echo ""
        echo "安装依赖:"
        echo "    pip install pytest Appium-Python-Client selenium"
        echo ""
        echo "秒杀 WebView 模板: templates/appium_seckill_h5.md"
        echo ""
    elif [[ "$KIND_HINT" == "ui_pytest_playwright" ]]; then
        echo "运行 UI 测试:"
        echo "    cd $OUT_DIR"
        echo "    export TEST_BASE_URL=http://your-server:5173   # Docker 前端；本地 run.py 用 5000"
        echo "    python3 -m pytest ${BASENAME}.py --collect-only -q   # 先确认用例已生成"
        echo "    python3 -m pytest ${BASENAME}.py -v --headed       # 有头浏览器（录制用）"
        echo ""
        echo "安装依赖（只需一次）:"
        echo "    pip install pytest-playwright"
        echo "    playwright install chromium"
        echo ""
        echo "生成 Allure 报告:"
        echo "    python3 -m pytest ${BASENAME}.py --alluredir=allure-results"
        echo "    allure serve allure-results"
        echo ""
    elif [[ "$KIND_HINT" == "api_pytest" ]]; then
        echo "运行 API 测试:"
        echo "    cd $OUT_DIR"
        echo "    python3 -m pytest ${BASENAME}.py --collect-only -q   # 先确认用例已生成（不访问网络）"
        echo "    export TEST_BASE_URL=http://你的服务:端口   # 有后端时再设"
        echo "    python3 -m pytest ${BASENAME}.py -v"
        echo ""
        echo "安装依赖:"
        echo "    pip install requests pytest"
        echo ""
        echo "生成 Allure 报告:"
        echo "    python3 -m pytest ${BASENAME}.py --alluredir=allure-results"
        echo "    allure serve allure-results"
        echo ""
    else
        echo "运行测试:"
        echo "    cd $OUT_DIR"
        echo "    python3 -m pytest ${BASENAME}.py --collect-only -q   # 先确认用例已生成（不访问网络）"
        echo "    export TEST_BASE_URL=http://你的服务:端口   # 有后端时再设"
        echo "    python3 -m pytest ${BASENAME}.py -v"
        echo ""
        echo "生成 Allure 报告:"
        echo "    python3 -m pytest ${BASENAME}.py --alluredir=allure-results"
        echo "    allure serve allure-results"
        echo ""
    fi
fi

echo ""
echo "（若 IDE / 集成终端完全空白）下面文件中有与本次输出相同的全文："
echo "    cat \"$OUT_DIR/.last_run_message.txt\""
