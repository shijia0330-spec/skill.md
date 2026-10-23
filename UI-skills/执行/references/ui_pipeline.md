# UI 标准流水线（默认路径）

**声明式 spec 直出 pytest ≠ 完整 E2E 回归。** 默认走「spec → 生成 → pytest」；复杂模块可接 `page_to_ui_cases` → 评审。

| 模式 | 何时用 |
|------|--------|
| **标准** | P0 准出、CI 回归 |
| **冒烟** | Day-1 连通性（`templates/ui_smoke_one_page.md` 等） |

默认环境：**`TEST_BASE_URL`** · **`TEST_USERNAME`** / **`TEST_PASSWORD`**

---

## Step 0：环境与登录态

```powershell
$env:TEST_BASE_URL = "http://your-server:5001"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
$env:UI_STORAGE_STATE = "output/.auth/ui_storage.json"
python3 UI-skills/执行/scripts/save_ui_storage_state.py   # 首次可选
```

---

## Step 1～2：页面分析（推荐 DOM 扫描）

```bash
python3 UI-skills/分析/scripts/scan_page_dom.py \
  --url http://your-server:5001/login \
  --storage-state output/.auth/ui_storage.json \
  -o output/dom_scan/login.json

python3 codegen/page_to_ui_cases.py --inspect /dashboard -o output/ui_cases.json
playwright codegen http://your-server:5001/login
```

---

## Step 3～4：spec

- `templates/ui_smoke_one_page.md`
- `templates/ui_login_parametrize.md`

---

## Step 5～6：生成与执行（包根目录）

```powershell
python3 codegen/run_spec.py templates/ui_smoke_one_page.md -o output/ui_smoke_one_page.py
powershell -File run_pytest_ui.ps1 output/ui_smoke_one_page.py -v --headed
```

---

## 与 API 对称

| API | UI |
|-----|-----|
| `templates/api_smoke.md` | `templates/ui_smoke_one_page.md` |
| `auth_profiles/generic_rest.yaml` | `UI_STORAGE_STATE` + `ensure_logged_in` |
| `openapi_pipeline.md` | `ui_pipeline.md`（本文件） |

---

## 大批量 Markdown 用例

见 `UI-skills/转化/SKILL.md` → `md_cases_to_ui_spec.py` → `./generate.sh`
