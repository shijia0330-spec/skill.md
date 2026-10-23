---
name: failure-analysis
description: 失败分析 — 规则/AI 分析失败根因、5 大类分类、置信度、去重、覆盖率反推与自动报 Bug 草稿。
---

# 失败分析

测试跑完有失败——**自动分析根因**，分门别类，给出修复建议；并可**反推用例盲区**，自动写 Bug 草稿。

---

## 集成说明（pytest 已内置）

在 **`skills-专业版V3.0` 根目录或其子目录（含 `output/`）** 执行 pytest 时，**每条失败用例**会自动分析并写入：

| 项 | 说明 |
|----|------|
| JSON 报告 | `output/reports/failure_analysis.json` |
| Markdown 统计 | `output/reports/failure_stats.md` |
| 关闭 | `FAILURE_ANALYSIS=0 pytest ...` |
| 改目录 | `FAILURE_ANALYSIS_DIR=./my-reports pytest ...` |
| 脚本 | `defect-analysis/failure_analyzer.py`（规则引擎；无 LLM 也可跑） |

分析完成后仍由 `bug-reporter/defect_drafts.py` 写缺陷草稿；指纹算法与 `defect-sync` 一致。

---

## 使用方式

### 方式一：pytest 自动（默认）

```bash
./run_pytest.sh output/seckill_api_smoke.py -v
# 失败时自动生成 failure_analysis.json + failure_stats.md
```

### 方式二：AI 辅助深析（Chat）

```
@defect-analysis/SKILL.md

帮我分析这些失败用例。
报告在 output/reports/failure_analysis.json。
重点：
- test_login: 期望 200 实际 500
- test_register_dup: 断言用户名已存在失败
```

AI 应：读 JSON/日志 → 补全根因 → 输出覆盖率盲区与补用例建议 → 人工复核后再 `defect-sync push`。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 5 大类根因 + 置信度 + 指纹去重 | 执行测试（走 api-skills / UI-skills） |
| 覆盖率盲区反推 + 补用例建议 | 直接替代人工定级（须复核） |
| 自动创建 Bug 草稿（带去重） | 修产品代码 |

---

## 5 大类失败模式（规则引擎）

| 类别 | 说明 | 严重级别 |
|------|------|----------|
| **env** 环境 | 网络、服务未起、Token 过期 | Medium |
| **data** 数据 | 404 资源、数据缺失 | Medium |
| **code** 代码 | 500、403 权限 | High |
| **test_design** 测试设计 | 断言错、定位失败、422 参数 | Low～Medium |
| **unknown** 未知 | 规则未覆盖 | 视情况 |

### 按严重程度（缺陷定级 · 与 bug-reporter 对齐）

| 级别 | 条件 | 示例 |
|------|------|------|
| **P0 - 致命** | 核心功能完全不可用，无绕过 | 登录全挂、支付/下单不可用、数据丢失 |
| **P1 - 严重** | 核心功能异常，有临时绕过 | 登录偶发失败、列表缺关键字段 |
| **P2 - 一般** | 非核心功能异常 | 筛选无效、排序错误 |
| **P3 - 轻微** | UI/文案/体验 | 按钮文案、提示不清晰 |

规则引擎默认映射：`code` → High（多为 P0/P1）；`env`/`data` → Medium；`test_design` → Low。

### 按缺陷类型（报告维度）

| 类型 | 说明 |
|------|------|
| 功能缺陷 | 行为不符合需求 |
| 性能缺陷 | 超时、响应慢 |
| 安全缺陷 | 越权、鉴权失败 |
| 兼容性缺陷 | 特定浏览器/环境 |
| 数据缺陷 | 不一致、格式错 |
| 用例缺陷 | 脚本/断言问题，非产品 Bug |

### 按来源模块（秒杀示例）

从 `nodeid`、URL、页面路径推断：

| 模块 | 典型特征 |
|------|----------|
| 登录 | `/login`、`/api/auth/login`、`test_login` |
| 注册 | `/register`、重复用户名 |
| 商品 | `/products`、`/api/products` |
| 鉴权 | `/api/auth/profile`、401/403 |

---

## 置信度分级

| 置信度 | 条件 | 处理 |
|--------|------|------|
| **高（≥0.8）** | 明确错误模式 | 建议自动报 Bug |
| **中（0.5-0.8）** | 需确认 | 报 Bug，标注「待确认」 |
| **低（<0.5）** | unknown | 人工排查 |

---

## 覆盖率反推

分析失败/缺陷特征，反推**用例盲区**（写入 `failure_analysis.json` 的 `coverage_gaps`）：

| 缺陷特征 | 可能盲区 | 建议补充 |
|----------|----------|----------|
| 边界/422 集中 | 缺边界 trio | `V-xx` + `boundary_value_testing.md` |
| 仅 happy path 失败 | 缺异常流 | 错误密码、重复注册、空字段 |
| UI 定位失败 | UI 精简未覆盖改版 | `@UI-skills/自我修复`，补 `UI-SECKILL-*` |
| 401/403 集中 | 缺权限/鉴权 | `P-xx` 未登录访问、错误 Token |
| 超时/env | 缺非功能 | `N-xx` 或压测场景 |

**输出示例**（Markdown 报告 §覆盖率盲区）：

```markdown
## 覆盖率盲区
1. 注册模块：2 次「用户名已存在」断言失败 → 建议补 V-03 重复用户名（seed + POST /api/test/init）
2. 商品列表：定位失败 → 建议 UI-SECKILL-07 搜索 + 列表断言
3. 鉴权：401×3 → 建议 P-01 未带 Token 访问 /api/auth/profile
```

反馈给 `testcase-skills/生成` 下轮生成时覆盖。

---

## 去重

**自动（pytest 集成）**：指纹 = MD5(nodeid 片段 + 状态码 + 错误前 50 字符)。同一指纹只建议报一次 Bug；与 `defect-sync` 的 `sync_state.json` 一致。

**AI 辅助深析时**（Chat 模式，可叠加）：

| 规则 | 说明 |
|------|------|
| 堆栈前 3 行相同 | 视为同一缺陷 |
| 错误信息含相同关键字 | 合并为一项 |
| 同一接口/页面连续失败 | 合并为一项 |
| 同一文件近期改动引入 | 标注关联，避免重复报 |

---

## 输出格式（Markdown 报告模板）

AI 深析或人工汇总时，可输出如下结构（与 `failure_stats.md` 对齐）：

```markdown
# 缺陷分析报告

## 执行概况
- 总用例数：20
- 通过：17
- 失败：3
- 成功率：85%

## 失败分类（5 大类）
| 类别 | 数量 | 占比 |
| env | 0 | 0% |
| code | 2 | 67% |
| test_design | 1 | 33% |

## 按严重程度
- P0：1 · P1：1 · P2：1 · P3：0

## 按缺陷类型
- 功能：2 · 用例：1

## 按来源模块
- 登录：1 · 注册：2

## 去重结果
- 原始失败：3
- 去重后唯一缺陷：2

## 覆盖率盲区
1. 注册模块重复用户名 → 建议补 V-03（seed）
2. …

## 建议
1. 优先修复 P0 登录 500
2. 反馈 testcase-skills/生成 补边界用例
```

---

## 输出（文件）

| 文件 | 内容 |
|------|------|
| `failure_analysis.json` | 失败明细 + stats + **coverage_gaps** |
| `failure_stats.md` | 人类可读统计 + 盲区 |
| `output/bugs/BUG-*.md` | 缺陷草稿（conftest 联动） |

---

## 注意事项

1. **分析依赖日志**：pytest 须保留 longrepr；UI 失败建议开 `UI_LOCATOR_DEBUG=1`
2. **AI 判断非绝对**：规则/AI 分类仅供参考，提交工单前人工复核
3. **不要跳过复核直接报**：高置信度也建议看一眼复现步骤
4. **持续改进**：把 `coverage_gaps` 反馈到用例生成 Skill，下轮 PRD 覆盖盲区
