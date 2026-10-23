---
name: ui-planning
description: Plans pytest-playwright UI automation scope, pages, paths, browsers, and locator strategy before writing scripts. Use when UI E2E scope is unclear.
---

# UI 自动化 — 先划范围再写脚本

有页面、有用户故事，但还没定「测哪几条、用哪些浏览器、用啥定位策略」时，用这份做**可执行的测试计划**；产出让执行阶段能直接开写。

工具链默认：**Python + pytest-playwright**。

---

## 1. 计划里一般写清啥

**范围**  
哪些页面、哪几条主路径要自动化；不做的也写一句，省得后面扯皮。

示例：
```
 做：登录、商品列表、加入购物车、下单支付
 不做：密码找回、客服聊天（非核心流程）
```

**浏览器 / 设备**  
至少定：桌面的 Chrome 要不要、要不要带一台移动视口。全矩阵不是不行，得看时间。

```yaml
browsers:
  - chromium          # 必测
  - firefox           # 如果用户群 > 5%
  - mobile_chrome     # 仅首页 + 登录
viewport:
  - 1280x720          # 桌面
  - 375x667           # 移动端（iPhone SE 尺寸）
```

**定位策略**  
和团队说的 L1→L2→L3 一致：能 `data-testid`、role+name、label 就不要上来就长 CSS 或纯视觉。全员默认堆在 L3 上迟早崩维护。

```python
# L1（推荐）：data-testid
page.get_by_test_id("login-btn").click()

# L1（备用）：role + name
page.get_by_role("button", name="登录").click()

# L2（兜底）：带父级约束的 CSS
page.locator(".login-form button[type='submit']").click()

# L3（少用）：纯位置/截图匹配 — 前端一次改版就崩
```

**断言**  
页面级看什么：文案、URL、关键控件出现与否；别全是「没报错就行」。

```python
# 好的断言
expect(page.get_by_text("登录成功")).to_be_visible()
expect(page).to_have_url("**/dashboard")

# 不好的断言
# assert "成功" in page.content()  # 太宽泛，容易误判
```

**数据**  
账号从哪来、测完要不要删数据、脏数据怎么隔离。

**数据驱动合并（计划标注）**  
同一页面、同一操作序列、仅输入/期望不同 → 在计划里标注 **`parametrize 合并`**，执行阶段用一条 flow + 多组数据，勿复制多条 case id。示例：

```yaml
cases:
  - id: UI-LOGIN-001
    desc: "有效用户登录成功"
    data_driven: merge   # 与 UI-LOGIN-002 合并为 parametrize 一行
  - id: UI-LOGIN-002
    desc: "错误密码登录失败"
    data_driven: merge
```

细则：`UI-skills/执行/references/ui_data_driven.md` · 模板 `templates/ui_login_parametrize.md`。

---

## 2. 计划产出模板

写完计划后，输出一份结构化的 YAML，后续执行阶段可以直接用：

```yaml
# ui_test_plan.yaml
project: "电商前端V3"
browsers: ["chromium", "firefox"]
viewport: ["1280x720", "375x667"]

pages:
  - name: "登录页"
    path: "/login"
    cases:
      - id: "UI-LOGIN-001"
        desc: "有效用户登录成功"
        locator_strategy: "L1"
      - id: "UI-LOGIN-002"
        desc: "密码错误提示"
        locator_strategy: "L1"
  
  - name: "商品列表"
    path: "/products"
    cases:
      - id: "UI-PROD-001"
        desc: "分页加载更多"
        locator_strategy: "L2"

not_in_scope:
  - "密码找回"
  - "支付回调页（用 API 验证）"
```

---

## 3. L1 / L2 / L3 随口翻译

| 级别 | 大白话 | 稳定性 | 维护成本 |
|------|--------|--------|---------|
| L1 | 稳定的属性：testid、role、label、placeholder | 高 | 低 |
| L2 | 带着父节点缩小范围再找 | 中 | 中 |
| L3 | 截图、视觉兜底的方案，贵，少用 | 低 | 高 |

---

## 4. 输出给谁

执行侧的脚本生成、模板、`generate.sh`，都应以这份计划里的范围和优先级为准。

---

## 5. 底线

- 默认交付 **Python**，不把 `.spec.ts` 当主线（除非项目单独立项）
- 计划阶段就别承诺「全自动零维护」，视觉兜底要写清风险和评审人
