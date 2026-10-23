---
name: load-analysis
description: 压测目标分析 — 识别接口清单、性能指标、数据量级、瓶颈预判。
---

# 压测分析

识别压测目标，输出接口清单 + 性能指标 + 数据量级。

## 触发条件

当用户提到以下关键词时使用：压测、性能测试、并发、TPS、响应时间、瓶颈、负载。

## 做 / 不做

| 做 | 不做 |
|----|------|
| 从 PRD/接口文档提取压测接口清单 | 直接生成脚本（走执行/SKILL.md） |
| 预估并发量、TPS、响应时间目标 | 执行压测（走执行/SKILL.md） |
| 识别热点数据、瓶颈预判 | 分析压测报告（走报告/SKILL.md） |

## 输入

| 方式 | 用户给什么 |
|------|------------|
| **A. 接口文档** | OpenAPI / Swagger / 接口列表 |
| **B. 自然语言** | 「测下单接口，目标 200 并发，P95 < 500ms」 |
| **C. 已有用例** | 从 testcase-skills 产出的用例中选压测接口 |

## 工作流程

### Step 1：接口清单

从输入中提取所有待测接口，输出表格：

| 接口 | 方法 | 路径 | 权重 | 优先级 |
|------|------|------|------|--------|
| 登录 | POST | /api/auth/login | 1 | P0 |
| 商品列表 | GET | /api/products | 5 | P0 |
| 用户信息 | GET | /api/auth/profile | 1 | P1 |
| 销售下单 | POST | /api/sales/orders | 2 | P0 |

权重 = 该接口在真实场景中的访问频率比例。

### Step 2：性能指标

根据业务类型预估指标：

| 指标 | 目标值 | 说明 |
|------|--------|------|
| P95 响应时间 | < 500ms | 95% 请求在此时间内 |
| 错误率 | < 1% | HTTP 5xx + 业务错误 |
| TPS | 1000+ | 每秒事务数 |
| 并发用户 | 200 | 同时在线用户数 |

### Step 3：数据量级

| 数据 | 规模 | 准备方式 |
|------|------|----------|
| 商品数据 | 1000+ | `data_factory` 或 `POST /api/test/init` |
| 用户数据 | N ≥ 目标并发 | `templates/data_factory.md` → `users.csv`（`username, password` 明文） |
| 订单数据 | 清空 | 压测前 `data_factory --reset` 或 `--cleanup` |

**多用户压测对齐规则：**
- `data_factory.tables.users.count` **≥** 规划中的目标并发（记为 N）
- CSV 有效行数 = N；JMeter `threads` / k6 `concurrent` = N（或 ≤ N）
- 登录用 CSV 的 **明文 `password`**，勿用 `password_hash`
- 压测后执行 `python3 data_factory.py --cleanup`

### Step 4：瓶颈预判

按 [references/bottleneck-checklist.md](references/bottleneck-checklist.md) 逐项检查：

| 维度 | 预判 | 关注点 |
|------|------|--------|
| 数据库 | 高 | 下单接口写操作，可能锁表 |
| Redis | 中 | 库存扣减，高并发下可能热点 key |
| 网络 | 低 | 内网服务，带宽充足 |

## 输出

输出 `压测分析_<项目>_<日期>.md`，包含上述 4 个表格。
