# UI 精简步骤句式白名单（秒杀财务 Web）

与 `codegen/md_to_ui_automation.py` → `_parse_step_line()` **逐条对齐**。  
写 UI 精简用例时 **只使用下列句式**；未收录的写法会被忽略或解析错误。

**默认环境**

| 项 | 值 |
|----|-----|
| Web 前端 | `http://your-server:5173` |
| API | `http://your-server:5001` |
| 账号 | `admin` / `admin123` |
| 铺底 | `POST /api/test/init` |

---

## 0. 解析器行为速查

| 步骤类型 | 代码入口 | 产出 action / expect |
|----------|----------|----------------------|
| 带 path 的导航 | `导航至 \`/path\`` | `goto` 或 `ensure_logged_in` |
| 已登录 + path | `admin 已登录，导航至 \`/products\`` | `_nav_step` → `ensure_logged_in` / `goto` |
| 点击按钮 | `点击「…」` | `click` + `l1_role=button` |
| 填写字段 | `填写{label}为 {value}` | `fill` + `l1_label` |
| 留空 + 点击 | `{label}留空，点击「…」` | `fill` 空值 + `click` |
| 单选 | `{字段}选择 {值}` | `click_radio` |
| 列表预期 | `列表中出现 {文本}` | `expect: visible_text` |
| 校验预期 | `出现必填校验提示` | `expect: alert_visible` |
| 重复注册 | `出现用户名已存在` | `expect: visible_text` |
| 按钮可见 | `页面可见「登录」按钮` | `expect: role_visible` |
| 纯前提 | `admin 已登录`（无导航） | **跳过**，不生成 step |

**protected 路由**（`/login` 以外需登录态）：`/products`、`/register` 完成注册后等 → 有 `UI_STORAGE_STATE` 时优先 `goto` 复用 cookie。

---

## 1. 进入页面

| 句式 | 转化结果 |
|------|----------|
| `admin 已登录，导航至 \`/products\`` | `ensure_logged_in` + `path: /products` |
| `导航至 \`/login\`` | `goto`（或登录页走 `ensure_logged_in` 填表） |
| `导航至 \`/register\`` | `goto` |

**禁止**：`打开页面`、`进入商品管理`（无 path）

**示例（UI-SECKILL-06）**

```markdown
- admin 已登录，导航至 `/products`
- 页面可见「商品」
```

---

## 2. 点击按钮

| 句式 | 转化结果 |
|------|----------|
| `点击「登录」` / `点击「登 录」` | `click` button |
| `点击「注册」` | `click` button |
| `点击「确认」` / `点击「确定」` / `点击「提交」` / `点击「保存」` | `click` button（弹窗内可带 `scope: dialog`） |
| `点击「搜索」` / `点击「查询」` / `点击「重置」` | `click` button |
| `点击「退出」` / `点击「登出」` | `click` button |
| `点击「新增商品」` | `click` button；含「新增」时用 `l1_name_regex` |

**禁止**：

- `勾选列表中 2 条及以上记录`
- `记录均从列表移除`（这是预期，不是操作）

---

## 3. 填写字段（登录 / 注册 / 商品）

匹配正则：`填写|填入|输入` + `{label}` + `为|是|：|: ` + `{value}`

| 句式 | 转化结果 |
|------|----------|
| `填写用户名为 admin` | `fill` `l1_label=用户名` `value=admin` |
| `填写密码为 admin123` | `fill` `l1_label=密码` |
| `填写用户名为 skills-demo-{timestamp}` | `fill` `value=__ENV__:TEST_UNIQUE_ID` |
| `填写邮箱为 demo@example.com` | `fill` 字面量 |
| `填写商品名称为 测试商品` | `fill`；字面量 `秒杀演示商品` → `__ENV__:SECKILL_PRODUCT_NAME` |

**复合句须拆分**（转化器不支持一句多动作）：

```markdown
- 填写商品名称为 测试商品
- 点击「搜索」
```

**留空校验**（匹配：`{label}留空.*点击「{btn}」`）：

| 句式 | 转化结果 |
|------|----------|
| `用户名留空，点击「登录」` | `fill` 空 + `click` 登录 |
| `密码留空，点击「登录」` | 同上 |

**禁止**：

- `用户名已填，密码留空`（合并前提 — 拆成两句）
- `点击「登录」，用户名留空`

**示例（UI-SECKILL-02 登录成功）**

```markdown
#### UI-SECKILL-02 正确凭证登录进入商品列表 <!-- P0 -->

- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 admin123
- 点击「登录」
- 导航至 `/products`
- 列表中出现 商品
```

**示例（UI-SECKILL-03 错误密码）**

```markdown
- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 wrong-password
- 点击「登录」
- 出现必填校验提示
```

（若产品有明确 Toast，可写 `出现用户名或密码错误`。）

---

## 4. 单选 / 下拉（商品管理弹窗，二期）

匹配：`{字段 hint}选择 {值}` 或 `{字段 hint}选 {值}`  
当 hint 含 `角色|状态|类型|方式` 时 → `click_radio`。

| 句式 | 转化结果 |
|------|----------|
| `角色选择 customer` | `click_radio` value=customer |
| `状态选择启用` | `click_radio` value=启用 |

用例含「新增商品」且 blob 含「状态」但未写单选时，转化器可补默认 `状态=开启`（见代码 `_infer_dialog_title`）。

**禁止**：`角色选 customer，状态选启用` 合并一句

---

## 5. 预期（无独立操作）

| 句式 | 转化结果 |
|------|----------|
| `列表中出现 商品` | `expect: visible_text` text=商品 |
| `列表中出现 skills-seed-product-a` | `visible_text` → `__ENV__:SECKILL_SEARCH_NAME` |
| `页面可见「登录」按钮` | `expect: role_visible` button |
| `出现必填校验提示` / `出现必填` / `不能为空` | `expect: alert_visible`（默认匹配「请输入」） |
| `出现用户名已存在` / `出现用户名重复` | `expect: visible_text` text=用户名已存在 |
| `出现用户名或密码错误` | `expect: visible_text`（全文或关键词，以产品为准） |

**注意**：弹窗 CRUD 场景下，`alert_visible` 会自动加 `scope: dialog`（除「用户名已存在」类全局 Toast）。

---

## 6. 页面加载冒烟（避免 C 档被筛掉）

**不推荐**（易落 C 档，仅 `role_visible`）：

```markdown
- 导航至 `/login`
- 页面可见「登录」按钮
```

**推荐 A/B 档**（UI-SECKILL-01 / 02）：

```markdown
- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 admin123
- 点击「登录」
- 列表中出现 商品
```

**轻量校验**（空密码，UI-SECKILL-04）：

```markdown
- 导航至 `/login`
- 填写用户名为 admin
- 点击「登录」
- 出现必填校验提示
```

---

## 7. 商品列表筛选（UI-SECKILL-07 扩展）

| 句式 | 说明 |
|------|------|
| `填写商品名称为 测试商品` | 下一步须单独写 `点击「搜索」` |
| `点击「重置」` | 清空筛选 |

seed 搜索名可写固定字面量 `skills-seed-product-a` → 运行时 `SECKILL_SEARCH_NAME`。

---

## 8. 可跳过行（转化器忽略）

| 句式 | 说明 |
|------|------|
| `admin 已登录`（无「导航至/进入」） | 文档前提，不生成 step |
| `环境中已有 admin 账号` | 写在文档头「数据依赖」表 |

---

## 9. 字段 → 环境变量（与代码常量一致）

代码：`SECKILL_FIELD_ENV`、`SEED_LITERAL_ENV`、`ENV_LITERAL_VALUES`

| 表单 label | 环境变量 | 触发条件 |
|------------|----------|----------|
| 用户名 | `TEST_USERNAME` | 字面量 admin 等 |
| 用户名 | `TEST_UNIQUE_ID` | 值含 `{timestamp}` |
| 密码 | `TEST_PASSWORD` | — |
| 邮箱 | `TEST_EMAIL` | — |
| 商品名称 | `SECKILL_PRODUCT_NAME` | label=商品名称 |

**seed 字面量**

| 步骤中的字面量 | 环境变量 |
|----------------|----------|
| `skills-seed-product-a` | `SECKILL_SEARCH_NAME` |
| `skills-seed-dup-user` | `SECKILL_DUPLICATE_USERNAME` |
| `admin`（重复注册） | 固定值；需先 `POST /api/test/init` |

**环境变量字面量**

| 步骤字面量 | 环境变量 |
|------------|----------|
| `秒杀演示商品` | `SECKILL_PRODUCT_NAME` |
| `wrong-password` | `TEST_WRONG_PASSWORD` |

PowerShell 示例见 `codegen/md_cases_to_ui_spec.py` 内 `SECKILL_ENV_DOC`。

---

## 10. 完整用例 → 转化产物对照（UI-SECKILL-09）

**Markdown 步骤**

```markdown
#### UI-SECKILL-09 重复用户名注册失败 <!-- P1 -->

- 导航至 `/register`
- 填写用户名为 admin
- 填写密码为 admin123
- 点击「注册」
- 出现用户名已存在
```

**预期 ui_automation 片段**（示意）

```json
{
  "steps": [
    { "action": "goto", "path": "/register" },
    { "action": "fill", "l1_label": "用户名", "value": "admin" },
    { "action": "fill", "l1_label": "密码", "value": "admin123" },
    { "action": "click", "l1_role": "button", "l1_name": "注册" }
  ],
  "expect": [
    { "type": "visible_text", "text": "用户名已存在", "exact": false }
  ]
}
```

---

## 11. 自检：禁用模式（写完后 grep）

以下模式 **必须改写**，不得出现在 `-` 步骤 bullet 中：

```
旧 SPA 管理后台路由前缀
旧网关 admin 前缀路由
旧管理后台路由前缀
企业管理后台类文案
旧云服务注册表单字段（服务器名称、唯一标识、传输方式 SSE 等）
勾选.*条
.*已填.*留空
```

---

## 12. 相关文档

| 文件 | 用途 |
|------|------|
| `output_schema.md` | Markdown 段头 / 用例结构 |
| `selection_rules.md` | 标准 8 条筛选 |
| `../SKILL.md` | UI 精简工作流 |
| `templates/ui_login.md` | 登录 spec 标杆 |
| `templates/ui_smoke_one_page.md` | 商品列表冒烟 |
