# 从完整版筛选 UI 精简用例

源文档：`output/*_testcases.md`（testcase-skills/生成 产出）  
**默认示例**：秒杀财务系统 Web（`http://your-server:5173`）+ API（`http://your-server:5001`）

---

## 1. 默认条数（2026-07 调整）

| 场景 | 推荐条数 | 说明 |
|------|----------|------|
| **模块冒烟（默认）** | **8 条**（+ seed 时 **9 条**） | P0×4 + P1×4～5 |
| 链路跑通 | 3～5 | 仅验 md→spec→collect-only |
| 回归扩展 | 12～20 | 从完整版继续映射 |

**秒杀登录+商品列表标准 8 条**见下文 §4，写 UI 精简版时 **优先齐套 8 条**，不要长期停在 4～5 条。

---

## 2. 筛选漏斗

```text
完整版 N 条
  → 仅 UI 可操作（点击/填表/搜索/弹窗）
  → 默认 P0/P1（P2 按需）
  → 单页或 /login → /products 短链路可完成
  → 步骤可映射 step_vocabulary
  → 模块冒烟 = 8 条
```

---

## 3. 纳入 / 排除

### 纳入（须同时满足）

| # | 条件 |
|---|------|
| S1 | 有明确页面 path（`/login`、`/products`、`/register` 等） |
| S2 | 至少 1 个可解析 UI 动作（点击/填写/选择） |
| S3 | 优先级 P0 或 P1（模块冒烟） |
| S4 | 不依赖第二账号、断网、时钟篡改 |
| S5 | 步骤 ≤12 条 bullet |

### 排除

| 类型 | 示例 |
|------|------|
| 纯 API | D-02 无 Token 调 Profile（无页面） |
| 多角色权限矩阵 | 需 customer + admin 同时在线 |
| 并发/竞态 | 秒杀抢购并发 |
| 网络异常 | 断网重试 |
| 纯视觉/布局 | 间距、配色 |
| 不可自动化叙述 | 「勾选 2 条及以上」无具体控件 |
| 超长树形流程 | 拆成多条 UI-SECKILL-xx |

---

## 4. 秒杀财务 · 标准 8 条（齐套）

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

**UI-SECKILL-01 写法注意**：纯「页面可见登录按钮」易落 C 档；须加 **填写用户名为 admin → 点击「登录」** 或 **点击后取消/清空** 保证可转化。

**UI-SECKILL-09 数据**：步骤中用户名写已存在的 `admin`；铺底见 `POST /api/test/init` 或 `templates/data_factory.md`。

---

## 5. 档位松紧（与 md_ui_filter / md_to_ui_automation 对齐）

| 模式 | `--tier` | 适用 |
|------|----------|------|
| **默认（松）** | `A,B,C` | **模块冒烟 8 条**；含页面加载、轻断言 |
| 严 | `A,B` | CI 准出；仅登录/列表主路径 |
| 最严 | `A` | 首期试点 2～3 条 |

转化命令（**默认已含 C 档**）：

```powershell
python3 codegen/md_cases_to_ui_spec.py `
  -i output/seckill_ui_cases.md `
  -o templates/seckill_ui_from_cases.md `
  --module 秒杀 --tier A,B,C --priority P0,P1
```

| 优先级 | tier 倾向 |
|--------|-----------|
| P0 + 点击/填表/登录 | A |
| P1 + 校验/列表断言 | A/B |
| P0 + 仅导航+可见（无点击） | C → **须改写** 或依赖 A,B,C |
| 空态/纯展示 | C → 不进 UI 精简 8 条 |

---

## 6. 二期扩展（不进标准 8+1 条）

- 商品 CRUD 页面、秒杀下单页、财务凭证页
- 多角色（customer vs admin）切换
- 退出登录、修改密码、Profile 页字段展示
