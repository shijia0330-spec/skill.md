# 测试点有效性校验

> 示例业务：**电商秒杀与财务一体化系统**（`seckill_finance_system`）。

写每条检查点前、Step 6 全文扫描时，使用本章规则。  
**核心**：测试点 = 可验证行为，≠ 需求复述。

---

## 1. 快速判定表

| 句式 | 判定 | 处理 |
|------|------|------|
| 系统支持… | [FAIL] 功能描述 | 改为「在 X 条件下，验证 Y」 |
| 需要通过 JWT 登录 | [FAIL] | 改为「未带 Token 调用受保护接口时返回 401」 |
| 秒杀使用 Redis 扣库存 | [FAIL] | 改为「库存为 1 时两次并发下单，仅 1 单成功」 |
| 活动状态为进行中才可下单 | [FAIL] | 改为「活动 UPCOMING 时 POST 下单返回约定错误码」 |
| 输入合法数据 | [FAIL] 模糊 | 写具体值（如 username=`buyer01`，price=9.99） |
| 操作成功 | [FAIL] 模糊 | 写 HTTP 状态码 / 订单 status / Redis 库存值 |
| 当前时间 = start_time - 1s | [FAIL] 条件当操作 | 写 admin 造活动（start=now()+2s）→ sleep(1) → POST + 期望 4xx（见 `time_and_state.md` §1.1） |
| 当前时间早于 start | [FAIL] 缺 HOW | 写创建未来 start 的活动 + 立即 POST + 断言 4xx 与 error_code |

---

## 2. 场景与验证方式（高频）

**需求原文**：「用户注册默认角色为 customer」

```markdown
#### 新用户注册后角色为 customer
- 提交唯一 username、password≥6、合法 email，POST /api/auth/register
- 响应 201；随后 GET /api/auth/profile 中 role 为 customer

#### 重复用户名注册失败
- username 与库中已有用户相同
- 响应 400（或 409），不创建第二条用户记录
```

---

## 3. 优先级与互斥规则

**需求原文**：「秒杀活动未开始不可下单；进行中可下单；已结束不可下单」

```markdown
#### E-04 活动 UPCOMING 时拒绝下单（开始前约 1 秒）
- admin 已登录；创建活动 start_time=now()+2s，end_time=now()+3600s，绑定 product_id=P1，记录 activity_id
- customer 已登录；sleep(1)，GET 活动 status=UPCOMING（可选）
- POST /api/seckill/{activity_id}/{product_id} 返回 400/422，body 含活动未开始类 error；无 order_id

#### E-05 活动 ACTIVE 时允许下单
- admin 已登录；创建活动 start_time=now()+2s，seckill_stock=10，prepare-stock 成功
- customer 已登录；sleep(2) 至 status=ACTIVE，Redis 库存>0，未超限购
- POST 秒杀返回 200/201，含 order_id；GET 订单 status=pending（与 PRD 一致）

#### E-06 活动 ENDED 后拒绝下单
- admin 已登录；创建活动 start_time=now()-3600s，end_time=now()-2s
- customer 已登录；sleep(2) 或 GET status=ENDED
- POST 秒杀返回 4xx，body 含活动已结束类 error；不产生新有效订单
```

---

## 4. 三问自检（每条必过）

1. 执行后能判 PASS/FAIL 吗？  
2. 有 **触发条件** 和 **可观察结果** 吗？  
3. 换测试执行人能否照做？

---

## 5. 待澄清占位写法

PRD 模糊但必须占坑时：

```markdown
#### T-01 秒杀未开始时列表价格展示（待澄清）
- 商品已配置未来开始的秒杀，当前时间早于 start
- 预期：展示常规价或预告价 — **需产品确认**（见文末待澄清 #3）
```

文末：

```markdown
## 待澄清清单
| # | 问题 | 关联用例 |
|---|------|----------|
| 3 | 秒杀未开始时列表显示常规价还是预告？ | T-01, L-03 |
```
