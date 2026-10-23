---
name: api-analysis
description: API测试分析 — 解析 OpenAPI、识别依赖关系、推断接口调用链。
---

# API 分析

解析 OpenAPI 文档，提取端点信息，**自动推断接口依赖关系**，输出调用链。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 解析 OpenAPI/Swagger 文档 | 生成测试用例（走执行/SKILL.md） |
| 推断接口依赖关系（4 种策略） | 执行测试（走执行/SKILL.md） |
| 输出调用链（拓扑排序） | |

---

## 工作流程

### Step 1：文档解析

从 OpenAPI/Swagger 提取：

| 信息 | 来源 |
|------|------|
| 端点列表 | paths 下的每个 path + method |
| 参数定义 | parameters + requestBody |
| 响应结构 | responses |
| 认证方式 | securitySchemes |

### Step 2：依赖关系推断（核心能力）

**4 种自动检测策略**，置信度从高到低：

| 策略 | 判定规则 | 置信度 | 示例 |
|------|----------|--------|------|
| **① 认证链** | 下游接口需要 auth，上游返回 token | 高 | `POST /login` → `GET /orders` |
| **② 路径参数引用** | 下游路径参数 = 上游响应字段 | 高 | `POST /orders` 返回 `order_id` → `GET /orders/{order_id}` |
| **③ 请求体引用** | 下游请求体字段 = 上游响应字段 | 中 | `POST /users` 返回 `user_id` → `POST /orders` body 含 `user_id` |
| **④ 命名启发式** | 路径前缀相同 + 资源名匹配 | 低 | `GET /users` 和 `POST /users` 属于同一资源 |

**生活例子**：像做菜——不能先炒蛋再开火。依赖图就是**菜谱顺序**。

### Step 3：拓扑排序

输出分阶段执行计划：

```
阶段1: [POST /login]                    ← 先拿 token
阶段2: [GET /users, POST /orders]       ← 可并行
阶段3: [GET /orders/{order_id}]         ← 必须等阶段2
```

同一阶段内的接口可并行执行，不同阶段必须串行。

### Step 4：变量提取点

标注每个接口需要提取哪些变量给下游使用：

| 接口 | 提取变量 | JSON Path | 下游使用 |
|------|----------|-----------|----------|
| POST /login | token | `$.data.token` | 所有需要认证的接口 |
| POST /orders | order_id | `$.data.id` | GET /orders/{order_id} |
| POST /users | user_id | `$.data.id` | POST /orders body.user_id |

---

## 依赖图示例

```
POST /api/auth/login
  ├──→ GET /api/auth/profile       (认证链)
  ├──→ POST /api/sales/orders      (认证链)
  │     └──→ GET /api/sales/orders/{id} (路径参数引用)
  └──→ DELETE /api/sales/orders/{id}    (认证链 + 路径参数引用)
```

---

## 输出

输出 `api_analysis_<模块>_<日期>.md`，包含：端点表 + 依赖关系 + 拓扑排序 + 变量提取点。
