# Playwright（Python）代码生成 — 给模型的系统侧说明

本仓库默认：**Python 3 + pytest + pytest-playwright**，用同步 API（`playwright.sync_api`）。**不**把 MidScene、纯 TS `.spec.ts` 当作默认交付。

---

## 1. 输入一般有啥

| 来源 | 用处 |
|------|------|
| 页面分析结果 | 控件列表、`locator_tiers`、置信度 |
| 用户说的验收话 | 通常落在 `main_content` |
| 上下文 | 页面类型、环境、是否需要登录 |

---

## 2. 定位顺序（和团队口头说的 L1→L2→L3 一致）

1. **优先**：`data-testid`、`get_by_role` + 可见名字、`get_by_label`、`get_by_placeholder`。  
2. **其次**：带范围的 `locator(...).filter`、精确文本。  
3. **最后**：截图、视觉类辅助——贵、易抖，**除非**分析结果写明只能这样，并在用例里注明。

---

## 3. 代码长什么样（示意）

```python
import re
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.case_id("TC-UI-001")
def test_login_happy_path(page: Page, base_url: str):
    page.goto(base_url + "/login")
    page.get_by_label("用户名").fill("demo")
    page.get_by_label("密码").fill("demo")
    page.get_by_role("button", name=re.compile("登录|登陆")).click()
    expect(page.get_by_text("工作台")).to_be_visible()
```

- 用 **`expect(locator)`** 做异步友好断言，少写裸 `assert page.inner_text()`。  
- `page.goto` 后该 `wait_for_load_state` 就写，别假设瞬时稳定。  
- 账号密码从 **环境变量** 读，示例：`import os; os.environ.get("E2E_USER")`。

---

## 4. 结构习惯

- **单测一个业务意图**；名字读得懂（中文 docstring 可以）。  
- 步骤重复三次以上再考虑 Page Object；小需求函数够用。  
- 稳定列表再 `.first`；否则写清楚为什么第一个就是你想要的。

---

## 5. 常见坑（生成时避开）

| 坑 | 咋回事 |
|----|--------|
| 全局 `text=提交` | 页面上两个「提交」就瞎点 |
| 不等多页跳转就断言 URL | 竞态 |
| 到处 `sleep(3)` | 掩盖性能问题还拖 CI |
| 把视觉 API 当默认 | 维护噩梦 |

---

## 6. 生成后自查（几条够用）

- [ ] 异步调用前面有 `await`（同步 API 里该同步的同步）  
- [ ] `expect` 从 Playwright 来，别从 fixture 里瞎掏  
- [ ] 选择器尽量稳定属性优先  
- [ ] 没有硬编码生产密码  
- [ ] `python3 -m py_compile` 能过

---

## 7. 输出形式

直接输出 **Python 源码**，用 Markdown 的 ```python 包起来；**不要**默认输出 TypeScript，除非项目另有分支约定。
