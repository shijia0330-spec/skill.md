# 自动化用例 · 编号注册表

> 前缀与模块、自动化产物一一对应；新增模块须在本表登记后再写用例。

| 前缀 | 模块 | 示例 | 自动化 |
|------|------|------|--------|
| L- | 登录 | L-01 正确登录 | api_auto + ui_auto |
| C- | 注册/创建 | C-01 合法注册 | api_auto |
| V- | 校验/边界 | V-04 错误密码 | api_auto |
| D- | 详情/Profile | D-01 Token 查 Profile | api_auto |
| P- | 权限 | P-01 越权 | api_auto |
| PROD- | 商品 | PROD-01 商品列表 | api_auto + ui_auto |
| SECK- | 秒杀 | SECK-01 下单 | api_auto |
| FIN- | 财务 | FIN-01 凭证 | api_auto |
| UI-SECKILL- | UI 精简 | UI-SECKILL-02 登录进商品页 | ui_auto |

完整示例：`examples/output_seckill_auth_testcases.md`

## 命名规则

- 格式：`{前缀}-{两位序号}`
- UI 精简：`UI-SECKILL-{两位序号}`（与源 L-/V- 追溯小表对齐）
- 禁止与已有编号冲突；扩展模块用新前缀，勿复用 L- 表示非登录场景
