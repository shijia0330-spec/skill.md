---
name: bug-reporter
description: Standardizes defect reports (repro steps, evidence, severity) for developers and trackers. Use when filing bugs from manual or automated findings.
---

# 缺陷报告 — 怎么写别人才愿意修

**版本**: v2.0  

自动化或手工测出问题，最后都要落成**可指派、可复现、带证据**的单子。这篇约定字段怎么填、严重级别怎么定。

---

## 集成说明（必读）

| 能力 | 本 Skill |
|------|----------|
| 产出 | Markdown 缺陷单（如 `bug_001.md`、`bug_list.md`） |
| **pytest 失败自动草稿** | 引擎根 `conftest.py` + `bug-reporter/defect_drafts.py`（见下节） |
| **pytest 失败自动分析** | 同 `conftest.py` → `defect-analysis/failure_analyzer.py`（`failure_analysis.json`） |
| **pytest 会话进度汇总** | 同 `conftest.py` → `progress-reporter`（`output/reports/progress.md`） |
| **推送到外部平台** | `defect-sync/` — 禅道 / 云效 / 自研 Webhook（见 `defect-sync/SKILL.md`） |
| **不提供** | 各平台密钥配置（走 `.env.local` 环境变量） |
| 对接方式 | 人工复制到工单系统，或 `defect-sync/scripts/defect_sync.py push` |

---

## pytest 跑完必出缺陷草稿（已内置）

在 **`skills-专业版V3.0` 根目录或其子目录（含 `output/`）** 执行 pytest 时，**每条失败用例**会自动写入草稿：

| 项 | 说明 |
|----|------|
| 默认目录 | `output/bugs/` |
| 单条文件 | `BUG-YYYYMMDD-NNN_<用例名>.md` |
| 汇总 | `output/bugs/bug_list.md` |
| 关闭 | `DEFECT_DRAFTS=0 pytest ...` |
| 改目录 | `DEFECT_DRAFT_DIR=./my-bugs pytest ...` |
| 推荐入口 | `./run_pytest.sh output/api_smoke.py -v` |

草稿含：**分流建议**（环境 / 脚本自愈 / 产品待确认）、失败堆栈、关联 nodeid。状态为 **Draft**，需人工确认后再提交工单。

`./generate.sh <spec> --report` 跑 pytest 时同样会写草稿（目录默认为 `<输出目录>/bugs`）。

---

## 这份材料解决啥

给开发一份「我看见了啥、你怎么再现、影响有多大」，减少来回问。附件该上就上，别光靠口头。

---

## 严重级别（先心里有个尺度）

级别决定排队顺序；别把小文案标成 P0，也别把支付挂了写成 Low。

| 级别 | 定义 | 响应要求 | 典型例子 |
|------|------|---------|---------|
| Critical | 系统不可用、数据丢失、核心功能瘫痪 | 立即处理，4小时内 | 服务无法启动、数据库连接失败、支付完全失败 |
| High | 重要功能失效，主要流程走不通 | 24小时内 | 上传功能报错、搜索结果不对、部分接口返回500 |
| Medium | 次要功能异常，有替代方案 | 3天内 | 页面排版错位、提示文字不对、排序有问题 |
| Low | 不影响使用，体验细节 | 下个版本 | 错别字、颜色不统一、字体大小不一致 |

---

## 缺陷类型

| 类型 | 说明 |
|------|------|
| 功能缺陷 | 功能没实现、实现错了、和文档不一致 |
| 界面缺陷 | 布局错乱、样式不对、交互异常 |
| 性能缺陷 | 响应慢、内存占用高、并发扛不住 |
| 安全缺陷 | SQL注入、XSS、未授权访问 |
| 兼容缺陷 | 某个浏览器不行、某个设备不行 |
| 数据缺陷 | 数据算错、数据丢失、数据不一致 |

---

## 报告模板

### 基本信息

| 字段 | 说明 |
|------|------|
| 缺陷编号 | BUG-YYYY-NNN，如 BUG-2026-001 |
| 标题 | 一句话描述问题，不要写"有问题"这种废话 |
| 严重程度 | Critical / High / Medium / Low |
| 缺陷类型 | 功能 / 界面 / 性能 / 安全 / 兼容 / 数据 |
| 所属模块 | 具体功能模块名 |
| 当前状态 | New → Open → In Progress → Fixed → Verified → Closed |
| 优先级 | P0 / P1 / P2 / P3 |

### 发现信息

- 发现时间：精确到分钟
- 发现人：谁发现的
- 发现方式：自动化测试 / 手工测试 / 用户反馈
- 关联用例：哪条测试用例触发的

### 问题描述

接口类缺陷和界面类缺陷的写法不一样。

**接口类缺陷**，需要写清楚：

```
接口地址：POST /api/seckill/activities/1/prepare-stock
请求方法：POST

请求头：
  Content-Type: application/json
  Authorization: Bearer <admin_token>

请求体：（无或按实现）

预期返回：200，Redis 库存与活动配置一致
实际返回：500，{"error": "Internal Server Error"}（Redis 未启动）
```

**界面类缺陷**（秒杀财务系统），需要写清楚：

```
操作路径：登录 → 商品管理 → 新增商品

操作步骤：
1. 浏览器打开 http://your-server:5000/login，admin 登录
2. 进入商品列表 /products
3. 填写商品名「秒杀演示-A」、价格 19.9、秒杀库存 10
4. 点击保存

页面现象：提交后无成功提示，控制台 403（customer 误用 admin 页面）
```

### 环境信息

| 字段 | 示例 |
|------|------|
| 操作系统 | macOS 14 / Windows 11 / Ubuntu 22.04 |
| 浏览器 | Chrome 131 / Firefox 129 / Safari 17 |
| 后端版本 | v2.3.1 |
| 前端版本 | v2.3.0 |
| 数据库 | MySQL 8.0.36 |
| 测试环境 | 开发环境 / 测试环境 / 预发环境 |

### 附件

- 截图：必须带，命名格式 `screenshot_BUG-2026-001_页面名.png`
- 日志：错误日志、控制台输出
- 录屏：复杂操作建议录屏

### 影响分析

- 影响范围：哪些功能受影响，哪些用户受影响
- 影响程度：能不能绕过，有没有临时方案

---

## 状态流转

```
New → Open → In Progress → Fixed → Verified → Closed
        ↓                        ↓
        └────── Reopen ←─────────┘
```

| 状态 | 含义 |
|------|------|
| New | 刚发现，还没确认 |
| Open | 确认是 bug，待开发人员修复 |
| In Progress | 开发人员正在修复 |
| Fixed | 开发人员已修复，等验证 |
| Verified | 验证通过，关闭 |
| Closed | 已关闭 |
| Reopen | 验证不通过，打回重修 |

---

## 统计报告

定期生成缺陷统计，格式如下：

```markdown
# 缺陷统计报告

统计周期：2026-05-01 ~ 2026-05-31
项目：电商后台

## 总体情况
- 新增缺陷：47
- 已修复：38
- 待修复：9
- 修复率：80.9%

## 按严重程度
| 级别 | 数量 | 占比 | 已修复 |
|------|------|------|--------|
| Critical | 3 | 6.4% | 3 |
| High | 12 | 25.5% | 10 |
| Medium | 24 | 51.1% | 19 |
| Low | 8 | 17.0% | 6 |

## 按类型
| 类型 | 数量 | 占比 |
|------|------|------|
| 功能 | 28 | 59.6% |
| 界面 | 10 | 21.3% |
| 性能 | 4 | 8.5% |
| 安全 | 2 | 4.3% |
| 兼容 | 3 | 6.3% |

## 待处理重点
1. BUG-2026-012：High，搜索结果为空时不显示提示（待修复）
2. BUG-2026-015：High，导出CSV中文乱码（待修复）
```

---

## 输出文件

| 文件名 | 内容 |
|--------|------|
| `bug_001.md` ~ `bug_NNN.md` | 单个缺陷报告 |
| `bug_list.md` | 所有缺陷汇总列表 |
| `bug_stats.md` | 缺陷统计报告 |

---

## 指纹去重 + AI 根因分析（核心能力）

本包内置的自动缺陷处理能力，减少误报和重复。

### 指纹去重

同一问题多次出现只报一次 Bug：

```
指纹 = MD5(接口路径 + 状态码 + 错误信息前 50 字符)

示例：
  POST /api/orders 500 "Internal Server Error" → 指纹 abc123
  POST /api/orders 500 "Internal Server Error" → 指纹 abc123（重复，跳过）
  GET  /api/orders 500 "Internal Server Error" → 指纹 def456（不同接口，新建）
```

### AI 根因分析

失败后自动分析根因，给出置信度分级：

| 置信度 | 条件 | 处理 |
|--------|------|------|
| **高** | 401/500/502/503 + 自愈成功 | 不报 Bug，标记 healed |
| **中** | 400 参数错误 + 有明确错误信息 | 报 Bug，标注"客户端错误" |
| **低** | 断言失败 + 可能是环境问题 | 报 Bug，标注"待确认" |

### 自动报告生成

```json
{
  "bug_id": "BUG-2026-001",
  "title": "POST /api/orders 返回 500",
  "severity": "High",
  "fingerprint": "abc123",
  "root_cause": {
    "type": "server_error",
    "confidence": "high",
    "analysis": "500 错误，连续 3 次重试后仍失败，非环境问题",
    "suggestion": "检查订单服务日志，可能是数据库连接池耗尽"
  },
  "healed": false,
  "attempts": [
    {"status": 500, "retry": 1},
    {"status": 500, "retry": 2},
    {"status": 500, "retry": 3}
  ]
}
```

### 飞书通知（可选）

推送成功后可选发飞书群通知（实现见 `defect-sync/scripts/adapters/feishu.py`）：

```bash
python3 defect-sync/scripts/defect_sync.py push output/bugs/ --platform custom --confirm --notify
```

环境变量：

| 变量 | 说明 |
|------|------|
| `FEISHU_WEBHOOK_URL` | 飞书 Bot Webhook |
| `FEISHU_NOTIFY_ON` | 可选，`High,Critical`（默认 Critical,High） |

或在 `.env.local` 配置后，缺陷草稿生成 + push 时加 `--notify`。

---

## 写好缺陷报告的原则

1. **标题要能看懂**——"提交订单报错"比"系统有问题"好十倍
2. **步骤要能复现**——按你写的步骤，别人能重现问题才算合格
3. **截图要清晰**——截图里要能看到错误信息，不要截半屏
4. **严重程度别乱标**——页面有个错别字不是 Critical，服务挂了才是
5. **修完要验证**——开发人员已修复不代表真修好了，你得再跑一遍
6. **别只报不跟**——报完缺陷要跟踪状态，不能报完就不管了
