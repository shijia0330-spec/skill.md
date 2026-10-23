---
name: ui-self-healing
description: UI测试自愈 — Web 端 L1 八种语义定位 + L2 DOM 推断 + 失败分类与收敛。元素变了自动换策略，失败截图。仅浏览器 E2E，不含 Appium。
---

# UI 脚本挂了 — 自愈与收敛

Playwright 跑红时：**运行时定位自愈**（L1 八种 + L2 推理）+ **失败分类与脚本补丁**。App 端走 `mobile-skills/`。

> 默认被测示例：**秒杀财务 Web**（`http://your-server:5173`）。

---

## 1. 运行时定位自愈（Web）

```
locator.click() 失败
  ↓ L1：testid → role → label → id/name → aria-label → text → placeholder → css
       成功 → healed=true, level=L1
  ↓ L2：scope 内 contains + 结构相似
       成功 → healed=true, level=L2, warning（建议人工复核）
  ↓ L3：input type 扫描（type=text / password）
  ↓ 仍失败 → 截图 + locator_fail_*.json + bug-reporter 草稿
```

| 能力 | 位置 |
|------|------|
| 策略文档 | `执行/references/locator_strategy_web.md` |
| 降级链 | `执行/references/locator_degradation_chain.md` |
| **离线 healer** | `执行/scripts/locator_healer.py` |
| **codegen 运行时** | `codegen/ui_lib/locator_resolver.py` |
| 设计期三层 | `分析/01_元素识别.md` → `locator_tiers.l1/l2/l3` |

### L1 八种策略

| # | 策略 | Playwright API |
|---|------|----------------|
| 1 | data-testid | `page.get_by_test_id(...)` |
| 2 | role + name | `page.get_by_role("button", name="登录")` |
| 3 | label | `page.get_by_label("用户名")` |
| 4 | id / name | `#id` / `[name="x"]` |
| 5 | aria-label | `[aria-label="login"]`（Vben 登录按钮常用） |
| 6 | text | `page.get_by_text("登录", exact=False)` |
| 7 | placeholder | `page.get_by_placeholder("请输入")` |
| 8 | CSS | `page.locator(".btn-primary")` |

### 两条运行时路径

| 路径 | 何时用 | 入口 |
|------|--------|------|
| **codegen pytest** | `./generate.sh` / `run_spec.py` 生成的脚本 | `codegen/ui_lib/locator_resolver.py` |
| **离线 healer** | 手写 pytest、单步调试 | `UI-skills/执行/scripts/locator_healer.py` |

### pytest 调用（离线 healer）

```python
import importlib.util
from pathlib import Path

_engine = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "locator_healer",
    _engine / "UI-skills/执行/scripts/locator_healer.py",
)
_healer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_healer)

hints = _healer.LocatorHints(
    testid="login-btn",
    role="button",
    name="登录",
    aria_label="login",
    label="用户名",
)
meta = _healer.click_with_heal(page, hints, primary_css="#old-submit")
# meta.healed, meta.strategy, meta.level, meta.attempts
```

本地演示：

```bash
python3 UI-skills/执行/scripts/locator_healer.py
```

### 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `UI_SELF_HEAL` | `1` | `0` 关闭降级 |
| `UI_HEAL_TIMEOUT_MS` | `500` | healer 单次尝试超时 |
| `UI_LOCATOR_DEBUG` | `0` | `1` 写 `locator_fail_*.json` 候选 |
| `UI_ENABLE_AI_LOCATOR` | `0` | L3 AI（roadmap） |

### 自愈日志示例

```json
{
  "healed": true,
  "strategy": "aria-label",
  "level": "L1",
  "attempts": [
    {"strategy": "css", "ok": false, "level": "L1"},
    {"strategy": "aria-label", "ok": true, "level": "L1", "ms": 42.1}
  ]
}
```

L2 命中时须人工复核，并推动前端补 `data-testid`。

---

## 2. 失败分类与脚本补丁

| 现象 | 多半是啥 | 常见处理 |
|------|----------|----------|
| 找不到元素 | DOM 改了、testid 丢了 | 查 `output/ui_artifacts/locator_fail_*.json`；更新 spec `l1_*` |
| 超时 | 网络慢、动画、服务未起 | `page.wait_for_load_state`；确认 `TEST_BASE_URL` 可达 |
| L2 warning | 模糊命中 | 人工复核；改回 role+name 或补 testid |
| 数据不对 | 账号/铺底数据问题 | `POST /api/test/init`；换 `TEST_USERNAME` / seed |
| 断言文案不对 | 产品改 Toast | 改 expect 或 UI 精简步骤里的「出现…」 |

### 失败留证

- `conftest.py`：PNG + HTML → `output/ui_artifacts/`
- `locator_resolver` / `locator_healer`：`locator_fail_*.json`（候选节点 Top-K）
- session 结束：`bug-reporter` 自动写 `output/bugs/BUG-*.md`

### 秒杀常见补丁

| 场景 | 处理 |
|------|------|
| 登录按钮点不到 | 优先 `aria-label="login"`，勿用宽泛「登录」误点扫码 Tab |
| 商品列表空 | 先 `POST /api/test/init` 或检查 seed |
| 注册重复用户名无 Toast | 对齐 `出现用户名已存在`（见 `UI精简/references/step_vocabulary.md`） |

---

## 3. 和谁配合

| 环节 | Skill / 脚本 |
|------|----------------|
| 页面结构变了 | `UI-skills/分析/00_DOM扫描.md` 重扫 |
| trace / 录屏 | `UI-skills/执行/SKILL.md` Step 6 |
| 产品缺陷 | `bug-reporter` |
| spec 过时 | 改 `templates/ui_*.md` 的 `l1_label` / `l1_role` |

---

## 4. 底线

- 自动修是为了省时间，**不掩盖真实产品缺陷**
- L2 命中必须 warning，须人工复核
- **同一用例连续修 3 轮仍红** → 转人工，更新 UI 精简或 spec
- 禁止为通过测试删除断言或改成 `always_pass`

完整策略说明：`执行/references/locator_strategy_web.md`
