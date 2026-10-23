# 自动化用例 · 覆盖矩阵

> 在 `universal_coverage_matrix.md` A～I 维基础上，标注 **哪些维度必须能落到自动化**（API spec / UI spec）。

## 秒杀认证模块（基线）

| 维 | 自动化要求 | 秒杀示例 |
|----|------------|----------|
| A 正向 | 必转 API 或 UI 主路径 | L-01, C-01, D-01 |
| B 反向 | 必含可断言 4xx | V-01～V-04 |
| C 边界 | trio 可参数化 | V-02 密码长度 |
| D 权限 | 401/403 case | P-01 admin role, D-02 无 Token |
| H 契约 | OpenAPI 有则必 H | `mini_openapi_boundaries.json` |

## 自动化标注

评审表「标签」建议增加：

- `api_auto` — 可进 `generate.sh` / cases JSON
- `ui_auto` — 须先 UI精简再转化
- `manual` — 暂不自动化，评审表保留

商品 / 秒杀 / 财务模块在对应 PRD 中扩展矩阵。
