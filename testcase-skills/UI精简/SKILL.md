---
name: testcase-ui-slim
description: >-
  Converts full Markdown test case documents (testcase-skills/生成 output) into
  UI-automation-ready slim cases for md_cases_to_ui_spec pipeline. Use when user
  has *_testcases.md for manual review and needs *_ui_cases.md before UI-skills/转化.
---

# UI 精简用例 — 功能用例 → 可转 spec 的 Markdown

**版本**：2026-07 · **位置**：`testcase-skills/UI精简`  
**默认示例系统**：**秒杀财务系统**（`seckill_finance_system`）Web 前端 `http://your-server:5173`，API `http://your-server:5001`，账号 `admin` / `admin123`。

完整功能用例（评审/归档）与 UI 自动化用例是**两种交付物**。本 Skill 负责从前者提炼后者，供 `UI-skills/转化` + `codegen/md_cases_to_ui_spec.py` 消费。

---

## 能力边界

| 做 | 不做 |
|----|------|
| 从 `*_testcases.md` 筛 P0/P1、可点击/可填表的 UI 子集 | 替代 `testcase-skills/生成` 写完整用例 |
| 按 `md_ui_filter` 可解析格式重写步骤 | 保证完整版每条 1:1 全自动转 pytest 全绿 |
| 产出 `*_ui_cases.md` 到 `output/` | 手写 spec YAML（交给转化 Skill） |
| 指导一键命令跑通 spec → pytest | 立即执行被测环境（用户按需） |

---

## 在流水线中的位置

```text
① testcase-skills/生成   →  output/*_testcases.md   （完整 · 人工/评审）
② testcase-skills/UI精简  →  output/*_ui_cases.md     （本 Skill）
③ UI-skills/转化         →  templates/*_ui.md        （spec）
④ codegen/run_spec.py    →  output/*_ui.py
⑤ pytest                 →  执行（可选 --collect-only 验收集）
```

**铁律**：禁止把 `*_testcases.md` 直接喂给 `md_cases_to_ui_spec.py`（会解析失败或产出错误步骤）。

---

## 快速使用

```text
@testcase-skills/UI精简/SKILL.md
@examples/prd_mini_seckill_auth.md
@examples/output_seckill_auth_testcases.md
按本 Skill 产出秒杀 Web（登录 + 商品列表）UI 精简用例 → output/seckill_ui_cases.md
```

产出后跑通转化（**不执行浏览器**时可加 `--collect-only`）：

```powershell
# Step A：功能用例 → UI 精简（按本 Skill 写 md，或人工）

# Step B：UI 精简 → spec（默认含 C 档，模块冒烟 8 条）
python3 codegen/md_cases_to_ui_spec.py `
  -i output/seckill_ui_cases.md `
  -o templates/seckill_ui_from_cases.md `
  --module 秒杀 --tier A,B,C --priority P0,P1

# Step C：spec → pytest
python3 codegen/run_spec.py templates/seckill_ui_from_cases.md -o output/seckill_ui_from_cases.py

# Step D：仅验证收集（不连浏览器）
python3 -m pytest output/seckill_ui_from_cases.py --collect-only -q
```

**环境变量（有前端时 Step D 之后全量跑）：**

```powershell
$env:TEST_BASE_URL = "http://your-server:5173"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
$env:UI_STORAGE_STATE = "output/.auth/ui_storage.json"
```

---

## 工作流程（Step 0～5）

### Step 0：读完整用例 + 金样

1. 读源文档 `*_testcases.md`（完整版，如 `output/seckill_auth_testcases.md`）
2. 必读金样：`examples/output_seckill_auth_testcases.md`（结构与编号风格）
3. 读 `references/output_schema.md`（Markdown 结构）
4. 读 `references/step_vocabulary.md`（步骤句式 · 与 `md_to_ui_automation.py` 对齐）

**秒杀 UI 范围（默认）**：登录页 `/login`、商品列表 `/products`；注册页 `/register`（若有）。纯 API 用例（如 Profile 401）**不进** UI 精简版，除非产品提供对应页面。

### Step 1：筛选可自动化用例

加载 `references/selection_rules.md`，从完整版中选出 **标准 8 条**（模块冒烟默认）：

| 纳入 | 排除 |
|------|------|
| P0/P1，单页或登录→列表短链路可完成 | P3 纯体验、并发、断网 |
| 有点击/填表/搜索/弹窗 | 纯权限矩阵（需多账号 fixture） |
| 有明确页面 path（`/login`、`/products` 等） | 无 path、 buried 在评审表/矩阵自检 |
| 步骤 ≤12 条 bullet | 15 步以上树形流程（拆成多条 UI 用例） |

**条数约定**：模块冒烟 **固定 8 条**；若含 seed 依赖（重复注册名），**+1 条 → 9 条**（UI-SECKILL-09）。链路跑通可临时 3～5 条，交付前补齐。

#### 秒杀财务 · 标准 8 条（齐套参考）

| UI 编号 | 源编号 | 标题 | 优先级 |
|---------|--------|------|--------|
| UI-SECKILL-01 | L-UI-01 | 登录页加载-表单可交互 | P0 |
| UI-SECKILL-02 | L-01 | 正确凭证登录进入商品列表 | P0 |
| UI-SECKILL-03 | V-04 | 错误密码登录失败提示 | P0 |
| UI-SECKILL-04 | V-UI-01 | 用户名为空校验 | P1 |
| UI-SECKILL-05 | V-UI-02 | 密码为空校验 | P1 |
| UI-SECKILL-06 | P-UI-01 | 已登录打开商品列表页 | P0 |
| UI-SECKILL-07 | P-UI-02 | 商品列表可见表头或商品文案 | P1 |
| UI-SECKILL-08 | R-UI-01 | 注册页打开-表单可交互 | P1 |
| UI-SECKILL-09 | V-03 | 重复用户名注册失败（**seed**） | P1 |

**UI-SECKILL-01 写法注意**：纯「页面可见登录按钮」易落 C 档；须加 **填写用户名为 admin → 点击「登录」→ 若仍在登录页则点击「取消」或清空**（推荐写法见 §Step 3 示例 01）。

### Step 1c：标注数据依赖

产出 `*_ui_cases.md` 时，须在文档头增加 **数据依赖表**。

| 策略 | 含义 | 秒杀示例 |
|------|------|----------|
| **none** | 无需预置数据 | UI-SECKILL-01 登录页加载 |
| **runtime** | 执行前设环境变量 / `{timestamp}` | UI-SECKILL-08 注册新用户 `skills-demo-{timestamp}` |
| **seed** | 依赖铺底数据 | UI-SECKILL-09 重复用户名 `admin`；执行前 `POST /api/test/init` |

**seed / 铺底**：

```bash
curl -X POST "http://your-server:5001/api/test/init" -H "Content-Type: application/json" -d '{}'
```

转化后若用例含 seed 依赖，spec 可带 `setup: test_init` 或 `setup: data_factory`（见 `templates/data_factory.md`）。

**重复注册步骤写法**：

- 注册：`填写用户名为 admin`（已存在账号）→ 点击「注册」→ `出现用户名已存在` 或 `出现必填校验提示`（以产品文案为准）

### Step 1b：档位松紧

| 模式 | `--tier` | 何时用 |
|------|----------|--------|
| **默认（松）** | `A,B,C` | 模块冒烟 8 条；含页面打开、轻断言 |
| 严 | `A,B` | CI 准出，只要登录/列表主路径 |
| 最严 | `A` | 试点 2～3 条 |

`md_cases_to_ui_spec.py` **默认已是 `A,B,C`**。页面加载类若只有「可见按钮」会落 C 档 — **改写为「填一项 → 点登录 → 再清空或取消」**（见 `step_vocabulary.md` §6），或依赖 C 档转化。

### Step 2：写页面段头（必须）

每个页面一组 `###` + 路径引用块：

```markdown
### [图] login-page.png · 秒杀财务 > 登录

> 路径：`http://your-server:5173/login`
```

```markdown
### [图] products-page.png · 秒杀财务 > 商品列表

> 路径：`http://your-server:5173/products`
```

| 字段 | 规则 |
|------|------|
| `screenshot` | 有 PNG 写文件名；无则 `page.png` 占位 |
| `menu_path` | `·` 后菜单链，与评审表一致 |
| 路径 | **必须** 写 SPA 路由（`/login`、`/products`）；`base_url` 默认前端 5173 |

### Step 3：写用例条目（####）

**示例 A · 登录成功（UI-SECKILL-02）**

```markdown
#### UI-SECKILL-02 正确凭证登录进入商品列表 <!-- P0 -->

- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 admin123
- 点击「登录」
- 导航至 `/products`
- 列表中出现 商品
```

**示例 B · 错误密码（UI-SECKILL-03）**

```markdown
#### UI-SECKILL-03 错误密码登录失败 <!-- P0 -->

- 导航至 `/login`
- 填写用户名为 admin
- 填写密码为 wrong-password
- 点击「登录」
- 出现必填校验提示
```

（「出现必填校验提示」或「出现用户名或密码错误」等 — 以实际 Toast/表单文案为准，见 `step_vocabulary.md` §5。）

**示例 C · 已登录打开列表（UI-SECKILL-06）**

```markdown
#### UI-SECKILL-06 已登录打开商品列表 <!-- P0 -->

- admin 已登录，导航至 `/products`
- 页面可见「商品」
```

**编号**：`UI-SECKILL-{序号}` 或保留源编号 `L-01` 并在标题注明 UI 场景。  
**优先级**：`<!-- P0 -->` / `<!-- P1 -->` 必填。

### Step 4：步骤句式自检

每条 bullet 必须匹配 `references/step_vocabulary.md` 中**已支持**句式之一；不支持的改写法或暂不纳入 UI 精简版。

写完后对照：

- [ ] 无「勾选列表中 2 条及以上记录」类叙述句
- [ ] 无把多字段合并成一句（如「用户名 admin，密码 123，点登录」）
- [ ] 登录/注册步骤按「填写…为…」与「点击「…」」分行
- [ ] 预期用「列表中出现 XXX」「出现…提示」「页面可见「…」」等可解析句

### Step 5：输出与追溯

**默认路径**：`output/seckill_ui_cases.md`（或 `output/{模块}_ui_cases.md`）

文档头模板：

```markdown
# 秒杀财务系统 · 登录与商品列表 · UI 精简用例

| 项目 | 说明 |
|------|------|
| 源文档 | output/seckill_auth_testcases.md |
| 精简规则 | testcase-skills/UI精简 |
| 前端地址 | http://your-server:5173 |
| API 地址 | http://your-server:5001 |
| 测试账号 | admin / admin123 |
| 用例数 | 8 条（P0 4 · P1 4） |
| 数据依赖 | 见下表 |
| 用途 | md_cases_to_ui_spec → spec → pytest |

## 数据依赖

| UI 编号 | 策略 | 说明 |
|---------|------|------|
| UI-SECKILL-01～08 | none / runtime | 见各用例 |
| UI-SECKILL-09 | seed | 执行前 POST /api/test/init |

---

## 源用例追溯

| UI 编号 | 源编号 | 说明 |
|---------|--------|------|
| UI-SECKILL-02 | L-01 | 正确登录 |
| UI-SECKILL-03 | V-04 | 错误密码 |
| UI-SECKILL-09 | V-03 | 重复用户名 |
```

---

## 与完整版的差异（写给 AI）

| 完整版 `*_testcases.md` | UI 精简版 `*_ui_cases.md` |
|-------------------------|---------------------------|
| 需求追溯表、矩阵自检、待澄清 | 仅保留源追溯小表 |
| `####` 自然语言检查点 | `####` + **可解析** `-` 步骤 |
| 含 API-only（Profile 401 等） | **仅保留有页面的** P0/P1 |
| 权限/并发/断网 | 二期或手工 |
| 评审表多行 | 无评审表（回指源文档） |

**映射提示**：`output_seckill_auth_testcases.md` 中 L-01/V-04/V-03 等 **API 用例** 需改写成 **浏览器步骤**（填表 + 点击），HTTP 状态码写在完整版，不写进 UI bullet。

---

## 转化后预期产物

```text
output/seckill_ui_cases.md
    ↓ md_cases_to_ui_spec.py
output/_pipeline/seckill_ui_candidates.json
output/_pipeline/seckill_ui_automation.json
templates/seckill_ui_from_cases.md    ← spec 含 ensure_logged_in + /products 等
    ↓ run_spec.py
output/seckill_ui_from_cases.py
```

**合格 spec 特征**（转化成功自检）：

- YAML 含 `base_url: http://your-server:5173`（或你的前端地址）
- 可选 `storage_state: output/.auth/ui_storage.json`
- 登录类用例首步为 `goto /login` 或 `ensure_logged_in` + `/products`
- 填表步骤带 `l1_label`（用户名/密码）或 `l1_placeholder`
- `--collect-only` 收集数 ≥7（允许 1 条 C 档边界）

---

## 子文档索引

| 文件 | 用途 |
|------|------|
| `references/output_schema.md` | Markdown 结构 · md_ui_filter 解析约定 |
| `references/step_vocabulary.md` | 步骤句式白名单（与 codegen 对齐） |
| `references/selection_rules.md` | 从完整版筛选规则 · 标准 8 条 |
| `examples/output_seckill_auth_testcases.md` | 源用例结构与编号金样 |
| `templates/ui_smoke_one_page.md` | 单页冒烟 spec 对照 |
| `templates/ui_login.md` | 登录流程 spec 对照 |
| `UI-skills/转化/SKILL.md` | 下游：spec → pytest |

---

## AI 编辑器快捷引用

**只做 UI 精简（本 Skill）**：

```text
@testcase-skills/UI精简/SKILL.md
@examples/prd_mini_seckill_auth.md
@examples/output_seckill_auth_testcases.md
产出秒杀 Web UI 精简用例到 output/seckill_ui_cases.md，**标准 8 条** P0/P1，覆盖登录与商品列表
```

**精简 + 转化 + collect-only（跑通流程）**：

```text
@testcase-skills/UI精简/SKILL.md
@UI-skills/转化/SKILL.md
已有 output/seckill_ui_cases.md，执行 md_cases_to_ui_spec → run_spec → pytest --collect-only
```

---

## 质量清单（交付前）

- [ ] 每条 `####` 有 case_id、标题、优先级注释
- [ ] 每个页面段有 `### [图] …` + `> 路径：`（5173 前端路由）
- [ ] 步骤句式全部在 step_vocabulary 白名单内
- [ ] 源追溯表列明 UI 编号 ↔ 完整版编号（L-01、V-04 等）
- [ ] 未把完整版评审表/矩阵复制进 UI 精简版
- [ ] **模块冒烟齐套 8 条**（见上文标准 8 条表）
- [ ] 含 seed 的用例在文档头注明 `POST /api/test/init`
- [ ] 转化 `--collect-only` 收集数 ≥7
- [ ] 下游 `md_cases_to_ui_spec.py -i ...` 无报错
