# Web UI 元素定位降级链路

> 本包 codegen 运行时：`codegen/ui_lib/locator_resolver.py`（Playwright 同步）；离线脚本：`UI-skills/执行/scripts/locator_healer.py`

## codegen 运行时实现矩阵（2026-07）

`./generate.sh templates/ui_*.md` 生成的 pytest **走 ui_lib**，与 `locator_healer.py`（离线脚本）不是同一条路径。

| 层级 | ui_lib 运行时 | spec 怎么写 | 备注 |
|------|---------------|-------------|------|
| **CACHE** | ✅ | 不写，运行时 LRU | 键含 `registry_key` + l1 字段 |
| **L0_SEM** | ⚠️ 部分 | `scope` / `dialog_title` | 无 `when` 表达式引擎；弹窗 scope 见 `scopes.py` |
| **L1** | ✅ | `l1_label`、`l1_role`+`l1_name`、`l1_test_id` 等 | **推荐只写 L1** |
| **registry_key** | ✅ | `registry_key` + `selector_registry` | DOM 扫描 → `output/selector_registry.json` |
| **L2 contains** | ✅ | 可不写，失败自动降级 | XPath contains 推断 |
| **semantic** | ✅ | 可不写 | `get_by_text` / role 模糊匹配 |
| **L2.5 Scrapling** | ❌ roadmap | — | 需 Scrapling 服务，未接入 ui_lib |
| **L3 AI** | ❌ roadmap | — | 无 LLM 选元素 |
| **L4 坐标** | ✅ | 可不写 | `UI_L4_MAX_PER_CASE` 限流 |

环境变量：`UI_SELF_HEAL=0` 关闭降级（仅 L1）；`SELECTOR_REGISTRY_PATH` 覆盖注册表路径。

---

```
CACHE → L0_SEM(条件) → L1 → L2 → L2.5 → L3(AI) → L4(坐标) → NONE
```

从快到慢、从确定性到概率性；**单次定位总超时 3s**（可配置）。

---

## 0. CACHE（缓存层）

| 项 | 说明 |
|----|------|
| 键 | `页面URL : action : target`（target 取自 l1_name / l1_label / value 等） |
| 策略 | LRU，最多 **500** 条 |
| 行为 | 命中直接返回上次成功的策略名与选择器，零延迟 |

spec 侧仍写 **L1 字段**（`l1_label`、`l1_role`+`l1_name`）；缓存由运行时维护，不写进 Markdown。

---

## L0_SEM — 条件语义（可选）

在步骤带 `when` / `if_visible` / 弹窗 `scope: dialog` 时，先判定上下文再进入 L1。  
典型：Ant Design Modal 打开后再填「密钥名称」。

---

## L1 — 稳定选择器（最快，spec 优先）

V3.1 尝试顺序（语义 API 优先，CSS 最后）：

1. target 已带前缀：`text=` / `xpath=` / `role=` 直接使用  
2. `data-testid` → `get_by_test_id`（confidence 0.98）  
3. `role` + `name` → `get_by_role`（0.95）  
4. `label` → `get_by_label`（0.93）  
5. `l1_id` / `l1_name_attr` → `#id` / `[name="..."]`（0.92）  
6. `l1_aria_label` → `[aria-label="..."]`（0.90）  
7. `text` fuzzy → `get_by_text(..., exact=False)`（0.75）  
8. `placeholder` → `get_by_placeholder`（0.85）  
9. `l2_css` / 显式 XPath（0.70，最后兜底）  

**REST 页面锚点示例**

| 路由 | L1 锚点 |
|------|---------|
| `/login` | label「用户名」「密码」；button「登录」 |
| `/dashboard` | 文案「商品总数」 |
| `/products` | button「创建商品」；表头「商品名称」 |
| `/inventory` | 「库存管理」；button「入库」 |

---

## L2 — DOM 推断（contains + 结构相似）

在 **scope 根节点**（dialog / form / main）内，从 target/value 提取 token，生成：

- `contains(@id)` / `contains(@name)` / `contains(@aria-label)` / `contains(@placeholder)`  
- `contains(text())` XPath  
- 若 spec 有 `l1_role`：限定 tag（button/a/input）+ attrs 结构相似  

confidence ≤ 0.80；命中时 **warning log**，建议人工复核。

失败时写 `output/ui_artifacts/locator_fail_*.json`（候选节点 Top-K）。

---

## L2.5 — Scrapling 自适应（无 LLM）

1. 抓取页面 HTML，Scrapling 解析 DOM  
2. 用 L1/L2 候选找参考元素 → `find_similar(threshold≈0.15)`  
3. 从相似节点生成新 CSS → Playwright 回验  

比 L2 更准、比 L3 快。**需部署 Scrapling**；未安装时跳过。

---

## L3 — AI 辅助（两阶段）

| 子阶段 | 模型 | 条件 |
|--------|------|------|
| L3_TEXT | 文本 LLM（如 qwen-plus） | 剩余时间 ≥ 500ms |
| L3_VL | 视觉 LLM（如 qwen-vl-plus） | 截图 + 剩余时间 ≥ 1000ms |

从失败历史生成 ≤8 个 contains 候选。`enable_ai=False` 时 **整层跳过**。

---

## L4 — 坐标点击兜底（最后手段）

1. 关闭遮挡 Modal（Ant Design）  
2. JS 扫描可点击元素（button、a、[role=button]…）  
3. 过滤不可见/过小元素  
4. 评分：target 全文 +100；关键词 +30；id/class +20~50  
5. 得分 ≥ 20 → 点击元素中心；否则点第一个可点击元素  

**熔断**：单 step 最多 **1** 次 L4；单 case 累计 **3** 次报警。

---

## 关键参数

| 参数 | 默认值 |
|------|--------|
| 总超时 | 3000 ms |
| CACHE 上限 | 500 LRU |
| enable_ai | 环境变量 `UI_ENABLE_AI`，默认 false |
| L4 熔断 | step 1 / case 3 |

---

## 与 spec / SKILL 的关系

- **写 spec**：只填 L1（+ 必要时 `l2_css`）；不要默认写坐标。  
- **执行失败**：走 `UI-skills/自我修复`；运行时自动 CACHE → L1…→L4。  
- **NL 一句话**：`nl_ui_client.py` 解析后同样走本链路。

---

## 环境变量

```bash
export UI_LOCATOR_TIMEOUT_MS=3000
export UI_ENABLE_AI=false
export UI_L4_MAX_PER_STEP=1
export UI_L4_MAX_PER_CASE=3
```
