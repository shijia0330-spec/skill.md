# 秒杀财务系统 · 详细设计 · 用例输入约定

> 主文档：`examples/tech_mini_seckill.md`（包内练手）；完整设计见 `seckill_finance_system/` 仓库。

## 模块划分

| 模块 | 说明 | 用例前缀 |
|------|------|----------|
| 用户认证 | 注册/登录/Profile | L- / C- / V- / D- |
| 商品管理 | CRUD、库存 | PROD- |
| 秒杀活动 | 下单、限购 | SECK- |
| 财务凭证 | 采购/销售 | FIN- |

## 接口约定

- REST 基址：`http://your-server:5001`
- 鉴权：`templates/auth_profiles/generic_rest.yaml`
- 铺底：`POST /api/test/init`

## 产出

- 功能用例：`output/seckill_*_testcases.md`
- UI 精简：`output/seckill_ui_cases.md`
- API spec：`templates/seckill_*.md`
