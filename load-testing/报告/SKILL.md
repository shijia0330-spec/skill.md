---
name: load-report
description: 压测结果分析 — 解读指标、截图识别、生成 Markdown/HTML 报告、定位瓶颈、给出优化建议。压测截图分析、性能报告生成时使用本 Skill。
---

# 压测报告

压测流水线的最后一步：**把结果变成能评审、能归档、能给领导看的报告**。

支持两种输入：

| 输入类型 | 典型场景 |
|----------|----------|
| **指标数据** | JMeter/k6 跑完后的数字、日志、导出 CSV |
| **截图 + 说明** | 聚合报告截图、监控大盘、只有图没有原始数据 |

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 解读 RT / TPS / QPS / 错误率 | 执行压测（走 `执行/SKILL.md`） |
| 从截图识别工具与关键指标 | 规划压测场景（走 `规划/SKILL.md`） |
| 分层瓶颈推断与优化建议 | 编写 jmx / k6 脚本 |
| 输出 Markdown 或 HTML 报告 | |

---

## 快速使用

### 路径 A：完整流水线（推荐）

先走完 `分析 → 规划 → 执行`，再引用本 Skill，附上执行结果或导出文件。

```text
@load-testing/报告/SKILL.md

压测已跑完，工具 k6，场景登录接口阶梯 50→200。
附上聚合结果，请出 Markdown 报告 + 瓶颈与优化建议。
```

### 路径 B：只有截图（轻量入口）

```text
@load-testing/报告/SKILL.md

（粘贴 1～多张压测截图）
场景：秒杀登录接口峰值压测，JMeter 聚合报告 + CPU 监控截图。
请识别指标、分析瓶颈，输出 HTML 报告到 output/perf_report.html
```

### 路径 C：JTL / k6 JSON → HTML（codegen，无需 AI）

JMeter 或 k6 跑完后，用脚本填 `performance-report-template.html`：

```bash
# JMeter
python3 codegen/run_jmeter_perf.py
python3 codegen/perf_report_from_results.py \
  --jtl output/jmeter-results.jtl \
  --title "秒杀 API 压测（JMeter）" \
  --scene "登录+商品列表" \
  -o output/perf_report_jmeter.html

# k6（须 --summary-export；业务断言失败见 output/k6_check_failures.json）
k6 run --summary-export=output/k6_summary.json output/seckill_load.js
python3 codegen/perf_report_from_results.py \
  --k6 output/k6_summary.json \
  --title "秒杀 API 压测（k6）" \
  -o output/perf_report_k6.html
```

产出为可浏览器打开的 HTML；瓶颈/建议章节为模板化文案，**精细分析仍走路径 A/B**。

---

## 工作流

1. **读参考**
   - 截图识别：`references/screenshot-tools-guide.md`
   - 指标与瓶颈：`../references/bottleneck-checklist.md`
   - HTML 结构：`references/html-report-structure.md`
   - HTML 模板：`assets/performance-report-template.html`（仅替换占位，保留样式）

2. **识别输入**
   - 判断测试类型：负载 / 稳定 / 压力 / 突发并发
   - 从截图或文字提取：工具、场景、并发模型、RT（平均/P95/P99）、TPS/QPS、错误率、资源曲线
   - k6 业务断言失败时：读取 `output/k6_check_failures.json`（含 `url`、`status`、`body_preview`）

3. **分析（固定顺序）**
   ```
   现象归纳 → 资源层 → 中间件 → 数据库 → 应用代码
   ```
   每条结论必须：**现象 + 依据（哪张图/哪个数）+ 可能原因**，禁止无依据猜测。

4. **输出报告**
   - 未指定格式时默认 **Markdown**：`output/压测报告_<场景>_<日期>.md`
   - 用户要求 HTML / 给领导看时：填模板生成 `output/perf_report_<场景>.html`

---

## 核心指标（健康参考）

与 `ci-gate` 阈值对齐时，测试环境常用：

| 指标 | 说明 | 参考 |
|------|------|------|
| P95 RT | 95% 请求耗时 | ≤ 800ms（测试环境） |
| 错误率 | 失败请求占比 | ≤ 1% |
| TPS | 每秒事务数 | 对照业务目标，看拐点 |

报告里须写：**实测值 + 是否达标 + 与目标的差距**。

**衔接 CI 门禁**（codegen 已提供）：

```bash
python3 codegen/perf_metrics_to_ci_gate.py --k6 output/k6_summary.json -o output/perf_metrics.json --run-gate --env prod --write-bug
```

---

## 报告必备章节

### Markdown 版

1. 压测概要（时间、环境、工具、场景、并发模型）
2. 核心指标表（接口维度：并发、TPS、P95、错误率、结论）
3. 瓶颈分析（分层、有依据）
4. 优化建议（短期可执行 / 中长期）
5. 结论与后续（是否可上线、是否需复测）

### HTML 版

章节与 Markdown 一致，版式见 `references/html-report-structure.md`。

截图处理：

- 用户提供文件路径 → `<img src="相对路径">`
- 仅在对话里粘贴图片 → 在「截图说明」写清每张图内容，并注明需用户自行保存图片后替换占位

---

## 书写原则

- **客观**：只写截图和描述里能支撑的内容
- **可读**：给领导和开发看，术语带一句解释
- **可执行**：优化建议具体到配置项、SQL、索引、线程池等方向

---

## 资源索引

| 路径 | 用途 |
|------|------|
| `codegen/perf_report_from_results.py` | JTL / k6 JSON → HTML（路径 C） |
| `codegen/run_jmeter_perf.py` | JMeter：refresh Token + 执行 |
| `codegen/fetch_perf_token.py` | 压测前 Token（REST 登录 + 探针） |
| `output/k6_check_failures.json` | k6 业务断言失败明细（codegen 自动生成） |
| `references/screenshot-tools-guide.md` | JMeter / k6 / 云压测界面与指标识别 |
| `references/html-report-structure.md` | HTML 各区块填写说明 |
| `../references/bottleneck-checklist.md` | 瓶颈检查清单 |
| `assets/performance-report-template.html` | HTML 报告模板 |
