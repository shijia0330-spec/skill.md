# Markdown 候选 → ui_automation 转化模板（秒杀财务）

Agent 或人工把 **A/B 档候选** 写成 `ui_automation` JSON，再交给 `testcase_to_ui_spec.py`。

---

## 1. 登录页 · 表单（login_form）

**适用**：`L-01` 正确登录、`V-04` 错误密码

```json
{
  "name": "seckill_login_success",
  "ui_automation": {
    "name": "login_success",
    "steps": [
      { "action": "goto", "path": "/login", "wait_until": "domcontentloaded" },
      { "action": "fill", "l1_label": "用户名", "value": "admin" },
      { "action": "fill", "l1_label": "密码", "value": "admin123" },
      { "action": "click", "l1_role": "button", "l1_name": "登录" }
    ],
    "expect": [{ "type": "visible_text", "text": "商品", "exact": false }]
  }
}
```

---

## 2. 商品列表 · 已登录（products_list）

**适用**：`P-UI-01` 列表加载

```json
{
  "ui_automation": {
    "name": "products_list_smoke",
    "steps": [
      { "action": "ensure_logged_in", "path": "/products", "wait_until": "networkidle" }
    ],
    "expect": [{ "type": "visible_text", "text": "商品", "exact": false }]
  }
}
```

---

## 3. 注册 · 重复用户名（register_duplicate）

```json
{
  "ui_automation": {
    "name": "register_duplicate",
    "steps": [
      { "action": "goto", "path": "/register" },
      { "action": "fill", "l1_label": "用户名", "value": "admin" },
      { "action": "fill", "l1_label": "密码", "value": "admin123" },
      { "action": "click", "l1_role": "button", "l1_name": "注册" }
    ],
    "expect": [{ "type": "visible_text", "text": "已存在", "exact": false }]
  }
}
```

**铺底**：执行前 `POST /api/test/init`，确保 `admin` 已存在。

---

## 4. 参考 spec

- `templates/ui_login.md` — 登录双保险
- `templates/ui_smoke_one_page.md` — 单页商品列表冒烟
