# Markdown 用例输入结构约定（秒杀财务）

`md_ui_filter.py` 解析 **testcase-skills/UI精简** 产出的 Markdown。

---

## 1. 必备块

### 截图 / 页面段头

```markdown
### [图] login-page.png · 秒杀财务 > 登录

> 路径：`http://your-server:5173/login`
```

| 字段 | 来源 |
|------|------|
| `screenshot` | 段头 `*.png` |
| `menu_path` | `·` 后菜单链 |
| `page_path` | 引用块 path（如 `/login`） |
| `page_url` | 完整 URL |

### 用例条目

```markdown
#### UI-SECKILL-02 正确凭证登录 <!-- P0 -->

- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 admin123
- 点击「登录」
```

| 字段 | 来源 |
|------|------|
| `case_id` | `####` 后第一个 token |
| `title` | ID 后至 `<!--` 前 |
| `priority` | `<!-- P0 -->` |
| `steps` | `- ` 开头的行 |

---

## 2. 编号前缀（秒杀）

| 前缀 | 含义 | UI 倾向 |
|------|------|---------|
| L- | 登录/列表 | 高 |
| C- | 注册/创建 | 高 |
| V- | 校验 | 高 |
| P- | 页面/权限 | 中 |
| D- | 详情（多为 API） | 低 |

UI 精简编号：`UI-SECKILL-{nn}`。

---

## 3. 默认环境

| 项 | 值 |
|----|-----|
| 前端 | `http://your-server:5173` |
| API | `http://your-server:5001` |
| 账号 | `admin / admin123` |
