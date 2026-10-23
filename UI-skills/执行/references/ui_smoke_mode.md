# UI 冒烟模式（单 spec 直出）

**定位**：登录态有效、目标页可打开、关键按钮可点；适合 collect-only / Day-1。**不能**作为发版唯一门禁。

```powershell
$env:TEST_BASE_URL = "http://your-server:5001"
$env:TEST_USERNAME = "admin"
$env:TEST_PASSWORD = "admin123"
$env:UI_STORAGE_STATE = "output/.auth/ui_storage.json"

python3 codegen/run_spec.py templates/ui_smoke_one_page.md -o output/ui_smoke_one_page.py
powershell -File run_pytest_ui.ps1 output/ui_smoke_one_page.py -v --headed
```

升级标准流水线见 `references/ui_pipeline.md`。
