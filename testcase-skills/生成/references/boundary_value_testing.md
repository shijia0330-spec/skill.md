# 边界值测试指南

> 数值示例来自 **秒杀财务系统**：价格、库存、限购次数、活动时间等。

## 为何必做

需求常用「大于」「小于」「最多 N 次」「长度 1～50」等表述，只测「明显合法/明显非法」会漏掉 **临界值** 缺陷。

## 核心规则

**每个比较条件都要测：阈值上、阈值下、阈值上（等于边界）**（范围类测 min-1, min, min+1, max-1, max, max+1）。

## 速查表

| 需求表述 | 必备用例 |
|----------|----------|
| X > N | X=N+1（通过区）、X=N（边界）、X=N-1（另一侧） |
| X < N | X=N-1、X=N、X=N+1 |
| X ≥ N | N-1 拒绝、N 通过、N+1 通过 |
| X ≤ N | N-1 通过、N 通过、N+1 拒绝 |
| 长度 min～max | min-1 拒绝、min、min+1、max-1、max、max+1 |
| 每用户限购 N 件 | N-1 成功、第 N 次成功、第 N+1 次拒绝 |
| 秒杀库存 N | N-1 下单后剩 0、第 N 次成功、第 N+1 次失败 |

## 示例：秒杀活动时间边界

需求：仅当 `start ≤ now ≤ end` 时活动为 ACTIVE，可下单。

**禁止**只写「当前时间 = start_time - 1s」而不写 **如何造数、如何等待、如何断言**（见 `time_and_state.md` §1.1、`test_point_validation.md` §1）。

### 可执行写法（API 自动化推荐）

```markdown
#### E-04 [秒杀] 活动开始前 1 秒不可下单
- admin 已登录；POST 创建秒杀活动，start_time = now()+2s，end_time = now()+3600s，绑定 product_id=P1，记录 activity_id
- customer 已登录；sleep(1) 后 GET 活动详情 status=UPCOMING（或等价字段），确认距 start 约 1s
- POST /api/seckill/{activity_id}/{product_id}
- 响应 4xx（如 400/422），body 含「活动未开始」或等价 error_code；不产生有效 order_id

> 若环境无法精确卡点：降级为「start 在未来任意时刻立即下单拒绝」，标 `review_required: true`

#### E-05 [秒杀] 活动开始时刻可下单（库存充足）
- admin 已登录；创建活动 start_time = now()+2s，end_time = now()+3600s，seckill_stock=10，prepare-stock 成功
- customer 已登录；sleep(2) 至 now ≥ start（或 GET 活动 status=ACTIVE）
- POST /api/seckill/{activity_id}/{product_id}
- 响应 200/201，含 order_id；GET 订单 status=pending（与 PRD 一致）

#### E-06 [秒杀] 活动结束后 1 秒不可下单
- admin 已登录；创建活动 start_time = now()-3600s，end_time = now()-2s（已结束）
- customer 已登录；sleep(2) 后确认 now > end（或 GET 活动 status=ENDED）
- POST /api/seckill/{activity_id}/{product_id}
- 响应 4xx，body 含「活动已结束」或等价 error_code；不产生新有效订单
```

### 反例（Step 6 应拦截）

```markdown
#### 开始前 1 秒不可下单          ← [FAIL] 缺造数/接口/断言
- 当前时间为 start 前 1 秒，POST 秒杀下单，拒绝（活动未开始）
```

## 示例：商品价格非负

需求：商品 `price` 必须 ≥ 0。

```markdown
#### 价格为 -1
- admin POST /api/products price=-1，拒绝并提示

#### 价格为 0
- price=0，允许保存（若 PRD 允许零价）

#### 价格为 0.01
- 最小正价保存成功
```

## 示例：注册密码长度（≥6）

```markdown
#### 密码 5 位
- password=`12345`，注册失败

#### 密码 6 位
- password=`123456`，注册成功（其他字段合法）

#### 密码 7 位
- password=`1234567`，注册成功
```

## 与 Step 6 自检联动

生成完成后扫描 func_list 中：大于、小于、最大、最小、范围、N 次、限购、库存 —— 缺边界 trio 则 **补写** 检查点。
