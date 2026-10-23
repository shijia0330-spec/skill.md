---
kind: ui_pytest_playwright
base_url: http://your-server:5000
viewport:
  width: 1280
  height: 720
flows:
  - name: 登录参数化
    parametrize:
      - id: 正常登录
        vars: {username: admin, password: "123456"}
      - id: 错误密码
        vars: {username: admin, password: wrong}
      - id: 空密码
        vars: {username: admin, password: ""}
      - id: 空用户名
        vars: {username: "", password: "123456"}
    steps:
      - action: goto
        path: /login
      - action: fill
        l1_label: "用户名"
        value: "{username}"
      - action: fill
        l1_label: "密码"
        value: "{password}"
      - action: click
        l1_role: button
        l1_name: "登录"
    expect:
      - type: visible_text
        text: "仪表盘"
        exact: false
---

# UI 登录 — 参数化数据驱动

同一流程，4 组输入 → 4 条独立 pytest 用例。

```bash
./generate.sh templates/ui_login_parametrize.md
cd output && python3 -m pytest ui_login_parametrize.py -v
```

**parametrize 结构**：
- `id`：用例标识，用于 pytest 输出
- `vars`：变量字典，steps 中用 `{var}` 引用

**生成效果**：
```python
_PARAMS_flow_1 = [{"id": "正常登录", "vars": {...}}, ...]
@pytest.mark.parametrize('case', _PARAMS_flow_1, ids=[...])
def test_ui_flow_1(page: Page, case):
    _context = dict(case.get('vars', {}))
    page.get_by_label("用户名").fill(_fill_ui_var("{username}", _context))
```
