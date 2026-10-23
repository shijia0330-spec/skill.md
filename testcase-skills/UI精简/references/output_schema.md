# UI 精简用例 — 输出结构约定（秒杀财务）

与 `UI-skills/转化/references/md_case_schema.md`、`codegen/md_ui_filter.py` 解析器对齐。

---

## 1. 文件命名

| 类型 | 路径 | 示例 |
|------|------|------|
| 完整功能用例 | `output/{模块}_testcases.md` | `output/seckill_auth_testcases.md` |
| **UI 精简用例** | `output/{模块}_ui_cases.md` | `output/seckill_ui_cases.md` |

同一模块两种文件并存；UI 版在文档头 `源文档` 字段指向完整版。

---

## 2. 文档结构

```markdown
# 秒杀财务系统 · {模块} · UI 精简用例

| 项目 | 说明 |
|------|------|
| 源文档 | output/seckill_auth_testcases.md |
| 精简规则 | testcase-skills/UI精简 |
| 前端地址 | http://your-server:5173 |
| API 地址 | http://your-server:5001 |
| 测试账号 | admin / admin123 |
| … | … |

---

## 源用例追溯

| UI 编号 | 源编号 | 说明 |

---

### [图] login-page.png · 秒杀财务 > 登录

> 路径：`http://your-server:5173/login`

#### UI-SECKILL-02 正确凭证登录 <!-- P0 -->

- 导航至 `/login`
- …
```

**禁止**在 UI 精简版中包含：`## 用例评审表`、`## 通用覆盖矩阵自检`、`## 待澄清清单`（留在完整版）。

---

## 3. 段头 `### [图]`

```markdown
### [图] products-page.png · 秒杀财务 > 商品列表
```

| 部分 | 规则 |
|------|------|
| `[图]` | 固定前缀 |
| `*.png` | 截图文件名；无实物时可占位 `page.png` |
| `·` 后 | 菜单/模块路径 |

紧跟一行路径（**必需**）：

```markdown
> 路径：`http://your-server:5173/products`
```

解析器提取 `page_path` = `/products`。  
若只有相对 path：`> 路径：\`/login\`` 亦可。

---

## 4. 用例条目 `####`

```markdown
#### UI-SECKILL-02 正确凭证登录进入商品列表 <!-- P0 -->
```

| 字段 | 规则 |
|------|------|
| `case_id` | `####` 后**第一个** token；建议 `UI-SECKILL-{nn}` |
| `title` | ID 与 `<!--` 之间的标题 |
| `priority` | `<!-- P0 -->` 形式；缺省按 P2 处理 |

步骤：仅 `- ` 开头的 bullet，每条一行，**一句一动作**。

---

## 5. 秒杀财务默认

| 项 | 值 |
|----|-----|
| 前端 base_url | `http://your-server:5173` |
| API base_url | `http://your-server:5001` |
| 登录 | `admin / admin123` |
| 登录页 | `/login` |
| 商品列表 | `/products` |
| 注册页 | `/register`（若有） |
| storage_state | `output/.auth/ui_storage.json` |
| 铺底 | `POST /api/test/init` |

步骤中写「admin 已登录，导航至 `/products`」→ 转化器生成 `ensure_logged_in`。

---

## 6. 编号对照建议

| 完整版前缀 | UI 精简倾向 | 说明 |
|------------|-------------|------|
| L- 登录 | 高 | 填表 + 点击登录 |
| V- 校验 | 高 | 空字段、错误密码 |
| C- 注册 | 中 | 注册页 + 重复用户名 |
| D- Profile | 低 | 多为 API-only，无页面则跳过 |
| P- 权限 | 低 | 需多角色 fixture |
| 商品/秒杀/财务 | 二期 | 另开 UI 精简文档 |
