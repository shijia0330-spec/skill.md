---
name: ui-execution
description: UI/E2E 统一入口：URL/截图/自然语言 → 元素分析 → Playwright 用例与脚本 → 执行与报告；支持 generate.sh 与 nl_ui_client 一句话执行。Use for browser testing, Playwright, or one-sentence UI actions.
---

# UI 测试执行（统一入口）

**版本**：2026-07 · **规则** 1.0  

与 `testcase-skills/生成` 同级：**输入可以粗（一句话 / 一张图 / 一个 URL），产出要细（步骤表 → Playwright → trace/报告）**。

---

## 能力边界

| 做 | 不做 |
|----|------|
| 页面元素分析、`locator_tiers`、生成 pytest-playwright | 接口契约测试（走 `api-skills/执行`） |
| 声明式 `ui_pytest_playwright` spec + `generate.sh` | 无头业务逻辑修 bug |
| flow 级 **parametrize** 数据驱动（登录矩阵、筛选多组值） | 外部 CSV 批量驱动（API `data_source` 专有） |
| 自然语言一句话在真实浏览器执行（`nl_ui_client.py`，探索） | 强依赖未启动的前端时仍应提示先起服务 |

默认栈：**Python + pytest-playwright** + `codegen/ui_lib`。

---

## 四种输入（按场景选）

| 方式 | 用户给什么 | 推荐路径 |
|------|------------|----------|
| **A. 标准（默认）** | URL + 用例表 / 冒烟清单 | **`references/ui_pipeline.md`** → spec → pytest |
| **A′. 冒烟直出** | 单 spec、Day-1 连通性 | **`references/ui_smoke_mode.md`** + `run_pytest_ui.ps1` |
| **B. 自然语言一句话** | 「在系统上…」 | `nl_ui_client.py`（探索，非 CI） |
| **C. 截图 / 原型图** | 无稳定 URL | `分析/02_图片…`；**有 URL 时改走 `分析/00_DOM扫描`** |
| **D. 已有用例 JSON** | 评审过的 `ui_automation` | `testcase_to_ui_spec.py` → `./generate.sh` |

> **默认约定**：用户要 UI 自动化且未说「冒烟/直出」→ 走 **A 标准路径**。

---

## 标准流水线（Step 0～7）— 默认

```
页面/用例表 → ui_automation JSON → 评审 → spec → pytest → trace/报告 → 失败分流
```

| Step | 动作 | 子文档 / 命令 |
|------|------|----------------|
| **0** | `TEST_BASE_URL`、账号、`UI_STORAGE_STATE` | 见 `.env.example` |
| **1** | **spec 或草稿** | `templates/ui_*.md`，或 `page_to_ui_cases.py` |
| **2** | **对齐 DOM** | `playwright codegen $TEST_BASE_URL/login` |
| **3** | **评审** | 对应用例 ID |
| **4** | **spec** | 编辑/复制 `templates/ui_login_parametrize.md` 等 |
| **5** | **脚本** | `python3 codegen/run_spec.py templates/xxx.md -o output/xxx.py` |
| **6** | **执行** | `./run_pytest_ui.sh output/xxx.py -v`（Linux）或 `powershell -File run_pytest_ui.ps1 …`（Windows，**默认 Allure**） |
| **7** | **失败** | `output/ui_artifacts/` + `output/bugs/` → 自我修复 / bug-reporter |

**冒烟捷径**：`references/ui_smoke_mode.md`

---

## Playwright 脚本结构（生成器产出）

`codegen/run_spec.py` 生成的 UI pytest 通常包含以下块（见 `output/ui_smoke_one_page.py`）：

```text
文件头          # Auto-generated · ui_lib
BASE_URL        # os.environ TEST_BASE_URL
fixtures        # browser_context_args、铺底 _setup_test_data（可选）
步骤/期望 JSON  # _UI_STEPS / _UI_EXPECTS 或 parametrize 矩阵
test_*()        # 调用 run_ui_flow / run_ui_batch（heal=True）
spec 正文注释   # 原 templates/*.md 说明（便于 diff）
```

**典型测试函数**：

```python
def test_declarative_ui_flow(page: Page):
    """UI 声明式流程"""
    run_ui_flow(page, _UI_STEPS, expects=_UI_EXPECTS, base_url=BASE_URL, heal=True)
```

**parametrize 数据驱动**（`templates/ui_login_parametrize.md`）：同一 `run_ui_flow`，多组 `(steps, expects)` 由 `@pytest.mark.parametrize` 注入。

**执行测试**：

```bash
export TEST_BASE_URL=http://127.0.0.1:5173
export TEST_USERNAME=admin TEST_PASSWORD=admin123
./generate.sh templates/ui_smoke_one_page.md
./run_pytest.sh output/ui_smoke_one_page.py -v --alluredir=output/allure-results
python3 scripts/allure_fallback_report.py output/allure-results output/allure-report/standalone.html
```

| 报告 | 路径 |
|------|------|
| Allure（UI/API 共用目录） | `output/allure-report/standalone.html` |
| 失败截图/HTML | `output/ui_artifacts/` |
| trace | `playwright show-trace …` |

> 参考包曾用 `output/allure-report-ui/`；本包 **UI 与 API 统一** `output/allure-report/`，用 `--alluredir` 子目录或文件名区分批次即可。

---

## 路径一：声明式生成（冒烟 / 模板）

```powershell
$env:TEST_BASE_URL = "http://your-server:5001"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
$env:UI_STORAGE_STATE = "output/.auth/ui_storage.json"
python3 UI-skills/执行/scripts/save_ui_storage_state.py   # 首次可选
python3 codegen/run_spec.py templates/ui_smoke_one_page.md -o output/ui_smoke_one_page.py
./run_pytest_ui.sh output/ui_smoke_one_page.py -v --headed
# Allure：output/allure-report/standalone.html（关闭：-NoAllure）
```

> UI 脚本依赖 `codegen/ui_lib`，请在**包根目录**执行 pytest，不要 `cd output` 后再跑。

---

## 路径二：自然语言一句话（演示 / 探索）

```bash
# NL 服务就绪后（见 nl-one-shot/SKILL.md）
python3 nl_ui_client.py "登录系统，进入商品管理列表" --json
```

环境变量：`NL_API_URL`、`TEST_BASE_URL`、`TEST_USERNAME`/`TEST_PASSWORD`、`UI_STORAGE_STATE`。

---

## 子文档索引

| 文件 | 用途 |
|------|------|
| `01_Playwright代码生成_系统提示.md` | 模型侧约束 |
| `02_Playwright代码生成_用户任务模板.md` | 用户任务占位 |
| `03_分析摘要构建说明.md` | 拼 analysis_summary |
| `references/ui_pipeline.md` | **默认** 页面 → JSON → spec → pytest |
| `references/ui_smoke_mode.md` | UI 冒烟直出 |
| `04_执行与报告约定.md` | CI、trace、`run_pytest_ui.ps1` |
| `05_自然语言一句话执行.md` | NL 详细说明 |
| `references/locator_degradation_chain.md` | CACHE→L1→L2→L4 |
| `references/locator_strategy_web.md` | Web 七种策略 + L2 |
| `references/ui_data_driven.md` | parametrize + capture |
| `执行/scripts/locator_healer.py` | 离线自愈 |
| `执行/scripts/save_ui_storage_state.py` | 保存登录态 |

单页冒烟：`templates/ui_smoke_one_page.md`  
登录数据驱动：`templates/ui_login_parametrize.md`

---

## 环境约定

| 项 | 约定 |
|----|------|
| 登录态 | `UI_STORAGE_STATE` → `output/.auth/ui_storage.json` |
| 首次存态 | `python3 UI-skills/执行/scripts/save_ui_storage_state.py` |
| 弹窗步骤 | spec 加 `scope: dialog` + `dialog_title` |
| pytest cwd | **技能包根目录** `python3 -m pytest output/xxx.py` |

---

## 视频录制与设备模拟

Playwright 执行时可录屏，失败保留 trace：

```bash
# run_pytest_ui.ps1 默认 trace；录屏示例（pytest-playwright）
$env:PLAYWRIGHT_VIDEO = "on"
./run_pytest_ui.sh output/ui_smoke_one_page.py -v --headed
# 产出：output/ui_artifacts/ 或 test-results/ 下 video.webm
```

| 能力 | 配置 |
|------|------|
| 录屏 | `record_video_dir`（spec `meta.video` 或 pytest 插件配置） |
| 设备模拟 | `--device="iPhone 13"` 或 viewport `375x667` |
| 失败 trace | `playwright show-trace output/ui_artifacts/trace.zip` |

规划阶段在 `UI-skills/规划/SKILL.md` 定 viewport / 移动视口范围。

---

## 数据驱动（parametrize）

> 细则 **`references/ui_data_driven.md`** · 实现见 `codegen/run_spec.py` + `ui_lib`。

同一 flow、多组输入/期望 → **`parametrize`**，不要复制 steps。

---

## 自愈定位（Web · V3.1）

> `references/locator_strategy_web.md` · `codegen/ui_lib/locator_resolver.py` · `../自我修复/SKILL.md`

| 变量 | 默认 | 说明 |
|------|------|------|
| `UI_SELF_HEAL` | `1` | 关闭设 `0` |
| `UI_LOCATOR_DEBUG` | `0` | 写失败候选 JSON |

---

## AI 编辑器快捷引用

```text
@ui-exec/SKILL.md
@http://your-server:5001/dashboard
按 Step 0～7：先步骤表，再 spec 或 Playwright，给出 pytest 命令
```
