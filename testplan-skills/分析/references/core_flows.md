# 核心流程 — 方案与分析用

> 完整版见 `testcase-skills/生成/references/core_flows.md`。  
> 本文件供 **testplan-skills/分析** 锚定 In-Scope 与 **方案 §2.3** 追溯。

## 何时在分析/方案中使用

- PRD 有端到端业务描述  
- 简陋 PRD 只有模块名 → 从技术文档 §3 API 反推流程  
- 方案 §2.3 需求追溯需要「主路径」一行摘要  

---

## 财务 v1.1 — 流程1（developer 下单）

```markdown
### 流程1：developer 参与 ACTIVE 并下单
- 匿名浏览商品（GET /api/products）
  - 注册或登录（POST /api/auth/login → JWT）
    - 查看活动状态（GET /api//status/{aid}/{pid}）
      - ACTIVE 且库存>0
        - POST /api//{aid}/{pid} 下单
          - Redis 扣减成功，订单创建
      - UPCOMING / ENDED / 库存不足
        - 4xx，无有效订单
      - 已达限购（T-01 澄清后）
        - 拒绝并提示
```

**方案映射**：In-Scope「下单」+ 策略 L3；里程碑 W3。

---

## 流程2（admin 配置+预热）

```markdown
### 流程2：admin 配置活动并预热 Redis
- admin 登录
  - 创建活动（POST /api//activities）
    - 关联商品（POST .../api/products）
      - prepare-stock（POST .../prepare-stock）
        - Redis key 可查
      - Redis 不可用
        - 5xx，不误导成功
```

**方案映射**：In-Scope「配置」「Redis 预热」；里程碑 W2。

---

## 与 testcase-skills 的关系

| 阶段 | 用途 |
|------|------|
| testplan 分析 | `scope_hint.in_scope` 依据 |
| testplan 方案 | §2.3 追溯表「测试覆盖策略」 |
| testcase 生成 | 展开为 `### 流程N` 用例块 |

---

## 分析 YAML 字段（可选）

```yaml
core_flows:
  - id: F1
    name: "developer ACTIVE 下单"
    priority: P0
    milestone_hint: W3
  - id: F2
    name: "admin 配置+预热"
    priority: P0
    milestone_hint: W2
```

---

## 自检

- [ ] 每条 In-Scope P0 模块至少落在一个 flow 上  
- [ ] Out-of-Scope 模块未强行写入 flow  
- [ ] 流程终点可观测（HTTP 码 / 订单 / Redis key）
