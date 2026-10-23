---
kind: api_pytest
# 秒杀时间边界 E-04 / E-05 / E-06 — 须先启动 seckill_finance_system
base_url: http://127.0.0.1:5000
auth:
  type: bearer_login
  login_path: /api/auth/login
  username_field: username
  password_field: password
  username_env: TEST_CUSTOMER_USERNAME
  password_env: TEST_CUSTOMER_PASSWORD
scenarios:
  - name: E-04 开始前约1秒拒绝下单
    layer: E
    priority: P1
    trace: E-04
    steps:
      - action: sleep
        seconds: 1
      - method: GET
        path: /api/seckill/activities/__ENV__:ACTIVITY_ID
        expect_status: 200
        expect_json_subset:
          status: UPCOMING
      - method: POST
        path: /api/seckill/__ENV__:ACTIVITY_ID/__ENV__:PRODUCT_ID
        expect_status: 400
        expect_body_substrings:
          - 未开始
  - name: E-05 开始时刻允许下单
    layer: E
    priority: P1
    trace: E-05
    steps:
      - action: sleep
        seconds: 2
      - method: GET
        path: /api/seckill/activities/__ENV__:ACTIVITY_ID
        expect_status: 200
        expect_json_subset:
          status: ACTIVE
      - method: POST
        path: /api/seckill/__ENV__:ACTIVITY_ID/__ENV__:PRODUCT_ID
        expect_status: 201
  - name: E-06 结束后拒绝下单
    layer: E
    priority: P1
    trace: E-06
    steps:
      - action: sleep
        seconds: 2
      - method: GET
        path: /api/seckill/activities/__ENV__:ACTIVITY_ID
        expect_status: 200
        expect_json_subset:
          status: ENDED
      - method: POST
        path: /api/seckill/__ENV__:ACTIVITY_ID/__ENV__:PRODUCT_ID
        expect_status: 400
        expect_body_substrings:
          - 已结束
---

# 秒杀活动时间边界（E-04 / E-05 / E-06）

## 前置（每条 scenario 独立造数）

本 spec **不**在 YAML 内嵌 admin 造数（customer/admin 双角色切换需独立 session）。  
请按 profile 先跑造数脚本，再 `./generate.sh` + pytest：

```bash
cd skills-专业版V3.0

# E-04
python3 output/seckill_time_boundary_upcoming.py
./generate.sh templates/seckill_time_boundary.md
export TEST_BASE_URL=http://127.0.0.1:5000
export TEST_CUSTOMER_USERNAME=customer_01
export TEST_CUSTOMER_PASSWORD=pass1234
./run_pytest.sh output/seckill_time_boundary_spec.py -k E-04 -v

# E-05
python3 output/seckill_time_boundary_active.py
./run_pytest.sh output/seckill_time_boundary_spec.py -k E-05 -v

# E-06
python3 output/seckill_time_boundary_ended.py
./run_pytest.sh output/seckill_time_boundary_spec.py -k E-06 -v
```

**推荐一键回归**（含造数 + 断言，不依赖 spec 分步）：

```bash
./run_pytest.sh output/seckill_time_boundary.py -v
```

造数脚本写入 `output/test_seed.env`（`ACTIVITY_ID` / `PRODUCT_ID`），spec 路径用 `__ENV__:` 占位符读取。

## 与 ref 对齐

- 用例写法：`testcase-skills/生成/references/time_and_state.md` §1.1
- PRD 补全：`api-skills/执行/references/boundary_and_prd_supplement.md` §2.1
- 造数规划：`data-factory/规划/SKILL.md` §时间边界活动
