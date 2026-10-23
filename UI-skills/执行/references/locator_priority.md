# 页面定位优先级（Playwright · Web 端）

> 完整策略（七种 + L1–L4 运行层）：**[locator_strategy_web.md](locator_strategy_web.md)**  
> 可执行自愈：**`../scripts/locator_healer.py`**

针对 `seckill_finance_system` 的 Jinja 页面（`/login`、`/products`、`/seckill`）。

## 推荐顺序（七种 · Web）

1. **`data-testid`**（若模板已加）
2. **role + name** — `get_by_role("button", name="登录")`
3. **`label` 关联** — `get_by_label("用户名")`（见 `templates/ui_login.md`）
4. **placeholder** — `get_by_placeholder("请输入密码")`
5. **稳定 id** — `#username`（非动态 id）
6. **文本** — `get_by_text("商品")`
7. **CSS / XPath** — 最后手段

## 秒杀财务页面提示

| 页面 | 稳定锚点 |
|------|----------|
| /login | label「用户名」「密码」、按钮「登录」 |
| /products | 标题含「商品」 |
| /dashboard | 登录后「仪表盘」类文案 |
| /seckill | 秒杀列表或倒计时区域 |

## 失败时

1. 启用 `locator_healer.py` 或 `@UI-skills/自我修复/SKILL.md`
2. 用 Playwright trace 看是否跳转到 `/login`（会话过期）
3. 真是产品 bug → `bug-reporter`；脚本过时 → 更新 `locator_tiers`
