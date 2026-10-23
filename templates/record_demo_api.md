---
kind: api_pytest
base_url: http://your-server:5000
# 录屏专用：仅「匿名可访问」接口，避免依赖秒杀活动数据是否存在。
cases:
  - id: REC-001
    name: 商品列表
    method: GET
    path: /api/products
    expect_status: 200

  - id: REC-002
    name: 秒杀商品列表（公开接口）
    method: GET
    path: /api/seckill/list
    expect_status: 200
---

# 录屏演示用 API（秒杀财务系统）

录屏演示：在本包根目录执行 `./generate.sh templates/record_demo_api.md`，再 `cd output && python3 -m pytest record_demo_api.py -v`（需先启动 `seckill_finance_system`）。

采购、财务等管理员接口请用 `examples/cases_with_automation.json` 生成 spec（需 `TEST_USERNAME` / `TEST_PASSWORD`）。全量模板见 `templates/seckill_query_tests.md` 等。
