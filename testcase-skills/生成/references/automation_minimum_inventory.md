# 自动化用例 · 最低用例清单

> 认证模块 **自动化准出基线**（秒杀财务）；未覆盖不得标「可上 CI」。

| 编号 | 标题 | 优先级 | 自动化 |
|------|------|--------|--------|
| L-01 | 正确登录 JWT | P0 | api_auto |
| V-04 | 错误密码 401 | P0 | api_auto |
| C-01 | 合法注册 | P0 | api_auto |
| V-03 | 重复用户名 | P0 | api_auto + seed |
| D-01 | Token 查 Profile | P0 | api_auto |
| D-02 | 无 Token 401 | P0 | api_auto |

## UI 精简基线（8+1 条）

见 `testcase-skills/UI精简/SKILL.md` · UI-SECKILL-01～09。

## 扩展模块

商品 / 秒杀 / 财务：另开 PRD，在本表格式下追加 PROD- / SECK- / FIN- 行。
