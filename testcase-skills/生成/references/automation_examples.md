# 自动化用例 · 写法样例

> 完整功能用例 vs UI 精简用例 vs API case 三种写法对照（秒杀财务）。

## API 自动化（功能用例 bullet）

```markdown
#### L-01 正确凭证登录返回 JWT <!-- P0 -->

- admin / admin123 调用 POST /api/auth/login
- HTTP 200；响应含 token 字段
- token 可用于 GET /api/auth/profile
```

转化：`openapi_to_cases.py` 或手工 cases JSON → `./generate.sh templates/seckill_api_auth.md`

## UI 自动化（须 UI 精简）

功能用例里的 HTTP 状态码 **不要** 写进 UI bullet。改为：

```markdown
#### UI-SECKILL-02 正确凭证登录进入商品列表 <!-- P0 -->

- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 admin123
- 点击「登录」
- 列表中出现 商品
```

见 `testcase-skills/UI精简/SKILL.md` · `step_vocabulary.md`。

## 输入 PRD

`examples/prd_mini_seckill_auth.md` · 金样 `examples/output_seckill_auth_testcases.md`
