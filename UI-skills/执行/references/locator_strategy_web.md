# Web 端定位与自愈策略（Playwright）

> **适用范围**：`UI-skills/` · 浏览器 E2E（Chromium / WebKit / Firefox）  
> **不适用**：`mobile-skills/`（Appium 另有一套 L0–L5，见 mobile-skills/自我修复/SKILL.md）

本包 Web UI：**生成期**用 L1/L2/L3 三层写入 JSON；**运行期**用七种 Playwright 策略 + L2 结构推断（可选 L3/L4 接 NL/AI 服务）。

**对外 demo 路径**：`./generate.sh templates/ui_*.md` 生成的 Playwright 脚本会**自动**调用 `locator_healer`（`fill_with_heal` / `click_with_heal` / `select_with_heal`），无需手改 conftest。关闭自愈：`UI_SELF_HEAL=0`。

---

## 一、两种口径（对外说法统一）

| 口径 | 用途 | 内容 |
|------|------|------|
| **七种 Playwright 策略** | 宣传、README、抖音 | 写脚本 / 自愈时依次尝试的定位手段 |
| **L1 → L2 → L3 设计层** | 分析阶段 JSON | 每条控件的 `locator_tiers.l1/l2/l3` |
| **L1 → L4 运行层** | pytest 执行自愈 | 见第四节运行四层 |

---

## 二、七种策略（Web · Playwright）

**推荐尝试顺序**（语义 API 优先，CSS 最后）：

| # | 策略 | Playwright API | 稳定性 | 说明 |
|---|------|----------------|--------|------|
| 1 | data-testid | `page.get_by_test_id("login")` | ***** | 测试专用属性，首选 |
| 2 | role + name | `page.get_by_role("button", name="登录")` | ***** | 按钮、链接、输入角色 |
| 3 | label | `page.get_by_label("用户名")` | **** | 表单输入 |
| 4 | placeholder | `page.get_by_placeholder("请输入密码")` | **** | 无 label 时的输入框 |
| 5 | id | `page.locator("#username")` | **** | 稳定 id 可用；动态 id 慎用 |
| 6 | text | `page.get_by_text("登录", exact=False)` | *** | 按钮/链接文案 |
| 7 | CSS | `page.locator(".btn-primary")` | ** | 哈希 class 易挂，作兜底 |

**L1 稳定选择器层**：L1 内聚合 testid / role / label / text 等 Playwright 原生 API。

---

## 三、设计三层（分析 → 生成）

写入 `elements[].locator_tiers`（见 `分析/01_元素识别.md`）：

| 层 | 键 | 含义 |
|----|-----|------|
| L1 | `l1` | 稳定契约：testid、role、label、placeholder、稳定 id |
| L2 | `l2` | 结构推断：祖先锚点 + 文案 filter + 受控 CSS |
| L3 | `l3` | 视觉/AI 兜底，须 `fallback_only: true` |

---

## 四、运行四层（执行 → 自愈）

| 层 | 本包实现 | 说明 |
|----|----------|------|
| **L1** | `locator_healer.py` 七种策略 | 默认开启，无第三方依赖 |
| **L2** | `locator_healer.py` DOM 推断 | id/name/class/placeholder 模糊匹配 |
| **L3** | `locator_healer.py` input type 扫描 | 按 `type="text"` / `type="password"` 找输入框，兜底登录页 |
| **L3-AI** | 可选 NL/AI 服务 | `UI_ENABLE_AI_LOCATOR=1` + NL 服务（roadmap） |
| **L4** | 文档约定，默认关闭 | 坐标点击兜底；仅调试，生产慎用 |

---

## 五、pytest 集成

```python
from pathlib import Path
import importlib.util

root = Path(__file__).resolve().parents[2]  # 引擎根
spec = importlib.util.spec_from_file_location(
    "locator_healer",
    root / "UI-skills/执行/scripts/locator_healer.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

hints = mod.LocatorHints(
    testid="login-btn",
    role="button",
    name="登录",
    label="用户名",
    text="登录",
)
loc, meta = mod.resolve_locator(page, hints, action="click")
loc.click()
# meta["healed"], meta["strategy"], meta["level"]
```

环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `UI_SELF_HEAL` | `1` | `0` 关闭自愈，仅用 hints 第一条 |
| `UI_HEAL_TIMEOUT_MS` | `500` | 每层单次尝试超时（毫秒） |
| `UI_ENABLE_AI_LOCATOR` | `0` | `1` 时 L3 可走 NL API（需 `NL_API_URL`） |

---

## 六、与 App 端区分（对外必讲清）

| | Web（本文件） | App（mobile-skills） |
|--|---------------|----------------------|
| 引擎 | Playwright | Appium |
| 策略数 | 7 种 + L2–L4 | accessibility_id / id / xpath … |
| 自愈脚本 | `UI-skills/执行/scripts/locator_healer.py` | 平台原生定位器链 |

---

## 七、相关文件

| 路径 | 说明 |
|------|------|
| `UI-skills/自我修复/SKILL.md` | 自愈流程、日志、配置 |
| `UI-skills/执行/SKILL.md` | 脚本生成 + 集成说明 |
| `UI-skills/执行/scripts/locator_healer.py` | **可执行** Web 自愈 |
| `UI-skills/执行/references/locator_priority.md` | 秒杀财务页面速查 |
