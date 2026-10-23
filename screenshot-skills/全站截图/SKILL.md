---
name: screenshot-skills
description: 全站页面截图 — 批量截取 SPA 页面或本地 HTML 为 PNG，产出 manifest.json + INDEX.md。
---

# 全站页面截图

对已部署的 Web 系统或本地 HTML 文件批量截图，产出本地 PNG + 索引，供 testcase-skills/生成、UI-skills/分析、UI-skills/转化使用。

无 Figma / 静态原型时，用本 Skill 替代「原型截图」输入。

**核心特性：**
- 支持 URL 模式（已部署系统）和本地 HTML 模式
- 自动点击页面按钮（新增/编辑/查看等）截取弹窗，URL 和本地 HTML 均支持
- manifest.json 不暴露本地文件路径

---

## 快速使用

### A. URL 模式（已部署系统）

**自然语言示例**：

```text
@screenshot-skills/全站截图/SKILL.md
系统地址 http://127.0.0.1:8080，需要登录 admin/123456，把全站截图存到 output/site-screenshots/
```

```bash
pip install playwright pyyaml
playwright install chromium

# 方式 1：路由清单（推荐）
python3 screenshot-skills/全站截图/scripts/crawl_and_capture.py \
  --base-url http://your-server:8080 \
  --out-dir output/site-screenshots/demo \
  --routes-file screenshot-skills/全站截图/templates/routes.example.txt \
  --auth-profile screenshot-skills/全站截图/templates/auth_ui_login.example.yaml \
  --viewport 1440x900 \
  --wait-ms 1500

# 方式 2：爬侧栏菜单（无 routes 文件时）
python3 screenshot-skills/全站截图/scripts/crawl_and_capture.py \
  --base-url http://your-server:8080 \
  --out-dir output/site-screenshots/menu \
  --auth-profile screenshot-skills/全站截图/templates/auth_ui_login.example.yaml \
  --crawl-menu \
  --max-pages 200

# 方式 3：清单 + 爬菜单补漏
python3 screenshot-skills/全站截图/scripts/crawl_and_capture.py \
  --base-url http://your-server:8080 \
  --routes-file screenshot-skills/全站截图/templates/routes.example.txt \
  --crawl-menu \
  --out-dir output/site-screenshots/combined
```

**预探测路由（可选）**：先跑 `discover_routes.py` / `discover_sidebar.py` 生成 JSON，再 `--routes-file` 传入。

> **注意**：动态 SPA 无法保证一次爬全——Tab/抽屉/弹窗内页需单独写进 routes 或后续补拍。

### B. 本地 HTML 模式

```bash
# 自动扫描目录下所有 .html 文件
python3 screenshot-skills/全站截图/scripts/crawl_and_capture.py \
  --local-dir /path/to/html-files \
  --out-dir output/site-screenshots/local \
  --viewport 1440x900 \
  --wait-ms 1500

# 指定文件清单
python3 screenshot-skills/全站截图/scripts/crawl_and_capture.py \
  --local-dir /path/to/html-files \
  --out-dir output/site-screenshots/local \
  --routes-file screenshot-skills/全站截图/templates/local_routes.example.txt \
  --viewport 1440x900
```

### C. 秒杀财务 Web（侧栏菜单 + 弹窗）

```bash
# URL 模式：首次手动登录
python3 screenshot-skills/全站截图/scripts/capture_web_sidebar.py \
  --base-url http://127.0.0.1:5173 \
  --start-menu 商品管理 \
  --manual-login --headed \
  --storage-state output/.auth/seckill_web_auth.json \
  --out-dir output/site-screenshots/seckill-web

# 本地 HTML 模式
python3 screenshot-skills/全站截图/scripts/capture_web_sidebar.py \
  --local-dir /path/to/html-files \
  --out-dir output/site-screenshots/seckill-web
```

---

## 按钮弹窗截图

脚本默认自动点击页面上的操作按钮并截取弹窗，适用于所有模式（URL / 本地 HTML）。

**默认截取的按钮：**
新增、新建、创建、编辑、修改、查看、详情、删除、导出、导入
New、Create、Edit、View、Detail、Delete、Export、Import、Add

**自定义截取按钮：**
```bash
python3 crawl_and_capture.py \
  --local-dir /path/to/html-files \
  --capture-buttons "新增,编辑,详情"
```

**关闭按钮截图：**
```bash
python3 crawl_and_capture.py \
  --local-dir /path/to/html-files \
  --no-capture-dialogs
```

**弹窗截图逻辑：**
1. 遍历页面上可见的按钮
2. 点击按钮 → 等待弹窗渲染
3. 尝试截取 `[role="dialog"]`、`.ant-modal`、`.el-dialog` 等弹窗区域
4. 如果找不到弹窗选择器，截取整页作为兜底
5. 自动关闭弹窗（Escape 或关闭按钮）

---

## 工作流程

### Step 0：澄清输入

| 项 | 必填 | 说明 |
|----|------|------|
| base_url 或 local_dir | 是 | 二选一：测试环境地址 或 本地 HTML 目录 |
| 登录方式 | 多数 SPA 需要 | 表单登录 / Cookie / Storage State（仅 URL 模式） |
| URL/文件来源 | 三选一+ | 路由清单 / 侧栏 / 站内爬取 / 自动扫描 |
| 规模 | 建议 | 默认 --max-pages 500，大系统先小批试跑 |

### Step 1：选择 URL/文件发现方式

| 方式 | 参数 | 适用 |
|------|------|------|
| **路由清单**（推荐） | `--routes-file routes.txt` | 前端路由或菜单 path 列表 |
| **侧栏链接（爬菜单）** | `--crawl-menu` | 侧栏 nav / aside 有 `a[href]`（仅 URL 模式） |
| **站内 BFS** | `--crawl-bfs --max-depth 2` | 页面间跳转较多（仅 URL 模式） |
| **组合** | 清单 + `--crawl-menu` | 清单覆盖主路由，菜单补漏 |
| **自动扫描** | 无（本地模式默认） | 本地 HTML 目录中所有 .html 文件 |

### Step 2：执行截图

- 默认：视口截图（1440x900）
- 长页面：`--full-page`
- 渲染等待：`--wait-ms` 或 `--ready-selector`
- 调试模式：`--headed`
- 按钮弹窗：默认开启，`--capture-buttons` 自定义按钮列表

### Step 3：交付物

```
output/site-screenshots/<name>/
├── pages/*.png
├── manifest.json
└── INDEX.md
```

- manifest.json：文件名/URL、标题、状态、弹窗截图记录
- INDEX.md：人工浏览索引

**路径脱敏：** 本地 HTML 模式下，manifest.json 中只记录文件名（如 `page1.html`），不暴露本地文件系统路径。

### Step 4：接入用例流水线（可选）

1. 按模块划分子目录
2. 调用 testcase-skills/生成
3. 结合 UI-skills/分析/02_图片测试用例描述生成.md

---

## 大规模系统注意事项

- 先跑 20 页验证登录与渲染，再扩大规模
- 同 path 不同 query 会分别截图，必要时收敛 routes
- 多角色权限 → 分角色多次运行，输出到不同子目录
- 截图脱敏后再入库，manifest.json 不含敏感字段
- 当前脚本为串行执行，稳定性优先

---

## 参考文件

| 文件 | 用途 |
|------|------|
| `scripts/crawl_and_capture.py` | 主执行脚本（URL + 本地 HTML） |
| `scripts/capture_web_sidebar.py` | 秒杀财务 Web 侧栏截图（URL + 本地 HTML） |
| `scripts/discover_routes.py` | 预探测候选路由（输出 JSON） |
| `scripts/discover_sidebar.py` | 从侧栏提取路由（输出 JSON） |
| `templates/auth_ui_login.example.yaml` | 登录配置模板 |
| `templates/routes.example.txt` | URL 路由列表示例 |
| `templates/local_routes.example.txt` | 本地 HTML 文件列表示例 |
| `references/spa_limits.md` | SPA 限制与补拍策略 |

---

## 质量检查清单

- [ ] manifest.json 中 failed ≈ 0 或已记录原因
- [ ] INDEX.md 与 pages/ 数量一致
- [ ] 核心流程页面（登录、首页、主菜单）均有截图
- [ ] 按钮弹窗截图数量符合预期
- [ ] 截图路径符合 output/ 约定，未混入敏感数据
- [ ] 本地 HTML 模式下 manifest.json 未暴露本地路径
