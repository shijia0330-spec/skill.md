---
name: ui-dom-scan
description: 页面 DOM 扫描 — 用 Playwright 提取真实可交互元素，输出结构化 JSON 供 LLM 生成测试用例。
---

# DOM 扫描（页面分析前置步骤）

用 Playwright 打开页面，提取所有可交互元素的真实 DOM 信息，输出结构化 JSON。

**解决什么问题：**
截图分析（`02_图片测试用例描述生成.md`）靠 LLM 看图猜控件，定位器全凭猜测。DOM 扫描提供真实数据：`data-testid`、`role`、`label`、`aria-label`、按钮文案、disabled 状态、弹窗结构、路由链接。

**放在流程的哪个位置：**
```
页面 URL/本地 HTML → DOM 扫描 → LLM 分析（元素识别 + 用例描述） → Playwright 代码生成
```

---

## 快速使用

```bash
pip install playwright
playwright install chromium

# URL 模式
python3 UI-skills/分析/scripts/scan_page_dom.py \
  --url http://your-server:8080/login \
  --out output/dom-scan/dom_login.json

# 本地 HTML 模式
python3 UI-skills/分析/scripts/scan_page_dom.py \
  --file /path/to/page.html \
  --out output/dom-scan/dom_page.json

# 仅扫描可见元素
python3 UI-skills/分析/scripts/scan_page_dom.py \
  --url http://your-server:8080 \
  --visible-only \
  --out output/dom-scan/dom_visible.json

# 带登录态扫描
python3 UI-skills/分析/scripts/scan_page_dom.py \
  --url http://your-server:8080/dashboard \
  --storage-state output/.auth/login_state.json \
  --out output/dom-scan/dom_dashboard.json

# 强制重新扫描（跳过缓存）
python3 UI-skills/分析/scripts/scan_page_dom.py \
  --url http://your-server:8080/login \
  --no-cache
```

---

## DOM 缓存

重复扫描同一页面时，自动使用缓存（基于 URL 的 MD5），避免重复启动浏览器。

```bash
# 首次扫描（保存缓存）
python3 scan_page_dom.py --url http://your-server:8080/login

# 再次运行（使用缓存，秒级返回）
python3 scan_page_dom.py --url http://your-server:8080/login --out output/dom_login.json

# 缓存默认有效期 1 小时，自定义：
python3 scan_page_dom.py --url http://your-server:8080/login --cache-ttl 86400  # 24 小时

# 强制重新扫描
python3 scan_page_dom.py --url http://your-server:8080/login --no-cache
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--cache-dir` | `output/dom-cache/` | 缓存目录 |
| `--cache-ttl` | `3600` | 缓存有效期（秒） |
| `--no-cache` | false | 跳过缓存，强制重新扫描 |

---

## 输出 JSON 结构

```json
{
  "scan_info": {
    "source": "http://your-server:8080/login",
    "viewport": "1440x900",
    "visible_only": false
  },
  "summary": {
    "scan_time": "2026-06-30 15:00:00",
    "page": {
      "title": "登录",
      "url": "http://your-server:8080/login"
    },
    "summary": {
      "total_elements": 12,
      "by_type": {
        "button": 3,
        "input": 4,
        "a": 2,
        "select": 1
      },
      "locator_coverage": {
        "data-testid": "8/12 (66%)",
        "role": "12/12 (100%)",
        "label": "6/12 (50%)",
        "aria-label": "3/12 (25%)",
        "id": "10/12 (83%)",
        "name": "9/12 (75%)"
      },
      "disabled_elements": 1,
      "dialogs_found": 0,
      "routes_found": 5
    }
  },
  "elements": [
    {
      "tag": "input",
      "text": "",
      "type": "text",
      "name": "username",
      "id": "username-input",
      "class": "form-control",
      "role": "input",
      "data-testid": "login-username",
      "aria-label": null,
      "placeholder": "请输入用户名",
      "label": "用户名",
      "disabled": false,
      "css": "#username-input",
      "parent": {
        "tag": "div",
        "role": "div",
        "id": null,
        "class": "form-group"
      }
    }
  ],
  "dialogs": [],
  "routes": [
    {
      "path": "/register",
      "text": "注册",
      "visible": true
    }
  ]
}
```

---

## 扫描内容

| 扫描项 | 说明 |
|--------|------|
| **可交互元素** | button、input、textarea、select、a[href]、role 元素、tabindex 元素、contenteditable |
| **定位线索** | data-testid、data-test、data-cy、id、name、role、aria-label、label、placeholder、title |
| **CSS 选择器** | 优先 `#id`，无 id 时 `tag.class`（跳过哈希 class） |
| **父级锚点** | 父元素的 tag、role、id、class，用于 L2 推断 |
| **状态标记** | disabled、readonly、checked、selected |
| **弹窗/抽屉** | dialog、alertdialog、ant-modal、el-dialog 等 |
| **路由链接** | 页面内 `<a href="/">` 链接，用于 SPA 路由发现 |

---

## 给 LLM 当输入

扫描结果 JSON 直接喂给 LLM，替代纯截图分析：

```
你是测试开发，根据以下 DOM 扫描结果生成测试用例。

## 页面信息
- 标题: {page.title}
- URL: {page.url}
- 元素总数: {summary.total_elements}

## 定位覆盖
- data-testid: {locator_coverage.data-testid}
- role: {locator_coverage.role}
- label: {locator_coverage.label}

## 可交互元素
{elements 列表}

## 弹窗
{dialogs 列表}

## 路由链接
{routes 列表}

请生成：
1. 元素识别清单（按用户任务路径排序）
2. 建议测试场景（正向 + 反向 + 边界）
3. 每个元素的推荐定位策略（优先 L1）
```

**比纯截图好的地方：**
- 能看到 disabled 状态 → 生成禁用按钮的测试点
- 能看到 placeholder/label → 直接生成 `get_by_label` / `get_by_placeholder`
- 能看到 data-testid → 优先用最稳定的定位
- 能看到弹窗结构 → 知道页面上有弹窗需要测
- 能看到路由 → 知道有哪些页面可以跳转

---

## 参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--url` | - | 目标 URL（与 --file 二选一） |
| `--file` | - | 本地 HTML 文件路径 |
| `--out` | - | 输出 JSON 路径 |
| `--out-dir` | `output/dom-scan` | 输出目录（无 --out 时自动命名） |
| `--viewport` | `1440x900` | 视口尺寸 |
| `--wait-ms` | `1500` | 等待渲染毫秒数 |
| `--headed` | false | 有头模式（调试用） |
| `--visible-only` | false | 仅扫描可见元素 |
| `--storage-state` | - | 登录态 JSON 路径 |
| `--max-elements` | `500` | 最大元素数 |
| `--cache-dir` | `output/dom-cache/` | DOM 快照缓存目录 |
| `--cache-ttl` | `3600` | 缓存有效期（秒） |
| `--no-cache` | false | 跳过缓存，强制重新扫描 |

---

## 与选择器注册表的衔接

扫描结果可直接导入选择器注册表，供 POM 跨文件引用：

```bash
# 扫描
python3 scan_page_dom.py --url http://your-server:8080/login

# 导入注册表
python3 selector_registry.py import output/dom-scan/dom_login.json

# 查看注册表
python3 selector_registry.py list
```

---

## 与现有流程的衔接

| 现有步骤 | 加入 DOM 扫描后 |
|----------|----------------|
| `02_图片测试用例描述生成.md`（截图 → 文字描述） | 先跑 DOM 扫描，LLM 基于真实数据写描述 |
| `01_元素识别.md`（LLM 猜定位器） | 直接读 JSON 里的定位线索，不需要猜 |
| `执行/SKILL.md`（生成 Playwright 代码） | 用 JSON 里的 `data-testid`、`label`、`css` 生成代码 |

---

## 质量检查清单

- [ ] 扫描结果中 `total_elements` > 0（页面有内容）
- [ ] `locator_coverage` 中 `data-testid` 覆盖率 ≥ 50%（理想 ≥ 80%）
- [ ] 关键交互元素（提交按钮、主要输入框）在 elements 列表中
- [ ] 弹窗/抽屉在 dialogs 列表中
- [ ] 扫描结果 JSON 文件大小合理（通常 5KB-50KB）
