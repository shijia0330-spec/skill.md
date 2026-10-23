# UI 转化标准输入包（三件套 · 秒杀财务）

新项目接入 `UI-skills/转化` 时，优先凑齐 **四件套**。

---

## 1. 文件清单

| 序号 | 文件 | 必需 | 来源 |
|------|------|------|------|
| 1 | `output/seckill_ui_cases.md` | ✅ | `testcase-skills/UI精简` |
| 2 | `output/site-screenshots/seckill/pages/*.png` | 强烈推荐 | `screenshot-skills/全站截图` |
| 3 | `output/site-screenshots/seckill/manifest.json` | 强烈推荐 | 截图脚本 |
| 4 | `output/_pipeline/seckill_ui_cases_by_image.json` | 强烈推荐 | DOM 扫描或读图 |
| 5 | `output/dom_scan/{page}.json` | 可选 | `scan_page_dom.py` |

| 文件 | 用途 |
|------|------|
| `output/.auth/ui_storage.json` | Playwright `storage_state` |
| `templates/auth_profiles/seckill_web.yaml` | UI 登录捕获 Token |

---

## 2. 目录示例

```text
output/
├── seckill_ui_cases.md
├── _pipeline/seckill_ui_candidates.json
├── site-screenshots/seckill/
│   ├── manifest.json
│   └── pages/login.png, products.png
└── .auth/ui_storage.json
```

---

## 3. 筛选命令

```bash
python3 codegen/md_ui_filter.py \
  -i output/seckill_ui_cases.md \
  -o output/_pipeline/seckill_ui_candidates.json \
  --manifest output/site-screenshots/seckill/manifest.json \
  --specs-json output/_pipeline/seckill_ui_cases_by_image.json \
  --screenshots-dir output/site-screenshots/seckill/pages \
  --tier A,B --priority P0,P1 --summary
```

---

## 4. 新项目最短路径（秒杀）

```text
① examples/prd_mini_seckill_auth.md → testcase-skills 生成 → UI精简 → seckill_ui_cases.md
② screenshot-skills 对 http://your-server:5173 截图
③ md_ui_filter → md_to_ui_automation → testcase_to_ui_spec
④ run_spec.py → pytest
```
