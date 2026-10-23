---
name: progress-reporter
description: 测试执行进度汇总 — pytest 结束后输出通过/失败/跳过统计，支持终端、Markdown、JSON。用于查看进度、汇报通过率或复盘失败列表。
---

# 进度报告

pytest 跑完后，把**通过数、失败数、跳过数、耗时、失败列表**整理成可读摘要。与 `bug-reporter` 互补：进度报告做**会话级统计**；失败详细缺陷草稿仍走 `bug-reporter/defect_drafts.py`。

---

## 集成说明（必读）

| 能力 | 本 Skill |
|------|----------|
| 产出 | 终端摘要 + `progress.md` + `progress.json` |
| **pytest 结束自动报告** | 引擎根 `conftest.py` + `progress-reporter/session_report.py`（见下节） |
| **不提供** | 缺陷工单字段、禅道/云效推送 |
| 与缺陷草稿 | 同一次 pytest 先写进度报告，再写 `BUG-*.md`（若 `DEFECT_DRAFTS=1`） |

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 汇总通过 / 失败 / 跳过与总耗时 | 写缺陷工单字段（走 `bug-reporter`） |
| 终端摘要 + Markdown + JSON | 推送到禅道/云效（走 `defect-sync`） |
| pytest 结束自动写 `output/reports/` | 替代 pytest 自带 `-v` 实时输出 |

---

## 自动触发（已内置）

在 **`skills-专业版V3.0` 根目录或其子目录（含 `output/`）** 执行 pytest 时，会话结束会自动生成进度报告（与缺陷草稿并行）。

| 项 | 说明 |
|----|------|
| 默认目录 | `output/reports/` |
| Markdown | `output/reports/progress.md` |
| JSON | `output/reports/progress.json` |
| 关闭 | `PROGRESS_REPORT=0 pytest ...` |
| 改目录 | `PROGRESS_REPORT_DIR=./my-reports pytest ...` |
| 输出格式 | `PROGRESS_REPORT_FORMATS=terminal,markdown`（默认三项全开） |
| 推荐入口 | `./run_pytest.sh output/api_smoke.py -v` |

终端末尾会看到 `[progress-report]` 摘要行及文件路径。

---

## 手动调用（脚本/API）

```python
from pathlib import Path
import importlib.util

root = Path("skills-专业版V3.0")  # 引擎根
spec = importlib.util.spec_from_file_location(
    "session_report",
    root / "progress-reporter" / "session_report.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

reporter = mod.SessionProgressReporter()
reporter.add_result("test_login", "passed", 1.2)
reporter.add_result("test_order", "failed", 0.5, "AssertionError: 500")
print(reporter.format_terminal_report())
reporter.generate_markdown_report(mod.resolve_report_dir() / "progress_manual.md")
```

本地演示：

```bash
cd skills-专业版V3.0
python3 progress-reporter/session_report.py
```

---

## 报告内容

### 终端示例

```
========================================
测试进度报告
========================================
总计: 15  |  通过: 12  |  失败: 2  |  跳过: 1
通过率: 85.7%
总耗时: 45.3s

失败用例:
  test_register_with_invalid_email
    AssertionError: expected 'success', got 'error'
========================================
```

### Markdown 示例

`output/reports/progress.md`：

```markdown
# 测试进度报告

生成时间：2026-07-02 14:30:00

| 指标 | 数值 |
|------|------|
| 总用例数 | 9 |
| 通过 | 8 |
| 失败 | 1 |
| 跳过 | 0 |
| 通过率 | 88.9% |
| 总耗时 | 2.1s |

## 失败用例

### test_tc_auth_v03

- **nodeid**: `output/seckill_api_reviewed.py::test_tc_auth_v03`
- **耗时**: 0.05s
- **错误**:

\`\`\`
AssertionError: 期望 400，实际 422: {"error":"..."}
\`\`\`
```

### JSON 示例

`output/reports/progress.json`（CI / 看板可直接 `jq` 解析）：

```json
{
  "generated_at": "2026-07-02T14:30:00",
  "total": 9,
  "passed": 8,
  "failed": 1,
  "skipped": 0,
  "errors": 0,
  "pass_rate": 88.9,
  "duration_seconds": 2.147,
  "cases": [
    {
      "nodeid": "output/seckill_api_reviewed.py::test_tc_auth_l01",
      "status": "passed",
      "duration": 0.105,
      "error": ""
    },
    {
      "nodeid": "output/seckill_api_reviewed.py::test_tc_auth_v03",
      "status": "failed",
      "duration": 0.052,
      "error": "AssertionError: 期望 400，实际 422"
    }
  ]
}
```

**CI 常用**：

```bash
jq '.pass_rate, .failed' output/reports/progress.json
# 门禁：通过率 < 100 且 failed > 0 时失败
python3 -c "
import json, sys
p=json.load(open('output/reports/progress.json'))
sys.exit(1 if p['failed'] else 0)
"
```

与 `defect-analysis` 的 `failure_analysis.json` 区别：本文件是**会话级统计**（每条 case 一行）；失败根因/盲区见 `failure_analysis.json`。

---

## 与缺陷草稿的关系

| 能力 | 模块 | 产物 |
|------|------|------|
| 进度汇总 | `progress-reporter` | `progress.md` / `progress.json` |
| 缺陷草稿 | `bug-reporter` | `output/bugs/BUG-*.md` |

同一次 pytest：先写进度报告，再写失败缺陷草稿（若 `DEFECT_DRAFTS=1`）。

---

## 实现位置

| 路径 | 说明 |
|------|------|
| `progress-reporter/session_report.py` | 汇总逻辑与写文件 |
| 引擎根 `conftest.py` | pytest 钩子自动调用 |

---

## 设计原则

- **轻量**：仅标准库，无第三方依赖
- **默认开启**：与缺陷草稿一样，本地跑测即产出报告
- **可关闭**：`PROGRESS_REPORT=0` 仅保留 pytest 原生输出
