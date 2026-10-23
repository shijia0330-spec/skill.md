# 秒杀财务 · 方案扩展

单模块用 `scheme_template.md`；多模块（认证/商品/秒杀/财务）时在方案中增加：

- §1.4 分期执行（P0 认证 → P1 商品 → P2 秒杀）
- §2.4 核心流程锚点（注册登录、商品列表、下单）
- 准出：M1 `api_smoke` + M2 `ui_smoke_one_page`

样例：`examples/test-plan-example-seckill.md`
