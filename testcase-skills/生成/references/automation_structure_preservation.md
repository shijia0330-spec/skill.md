# 自动化用例 · 模块结构与前缀

> 编号前缀与 PRD 模块对齐，便于追溯与 `run_spec.py` 分 spec 生成。

| 模块 | 前缀 | 自动化产物 |
|------|------|------------|
| 用户认证 | L- / C- / V- / D- | `templates/seckill_api_*.md` |
| 商品 | PROD- | API + UI 商品列表 |
| 秒杀 | SECK- | API 下单链路 |
| 财务 | FIN- | API 凭证/报表 |
| UI 精简 | UI-SECKILL- | `output/seckill_ui_cases.md` → pytest |

结构保持规则仍见 `structure_preservation.md`；自动化线额外要求 **每条 P0 能在评审表标 `api_auto` 或 `ui_auto`**。
