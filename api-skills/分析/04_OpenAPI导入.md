# OpenAPI 导入

> **默认路径**不是「直接 import 出 pytest」，而是 **`api-skills/执行/references/openapi_pipeline.md`** 标准流水线：  
> OpenAPI → cases 草稿（H/E/X）→ 人工评审 → spec → pytest。

本文档说明 **底层 import 能力**；日常请优先走标准流水线或冒烟捷径。

---

## 标准流水线（推荐）

```bash
# Step 1：OpenAPI → cases 草稿
python3 codegen/openapi_to_cases.py -i openapi.yaml \
  -o output/cases_draft.json \
  --base-url http://your-server:5001 \
  --auth-profile templates/auth_profiles/generic_rest.yaml

# Step 2：评审 output/cases_draft.json 后 → api spec
python3 codegen/testcase_to_api_spec.py -i output/cases_draft.json -o templates/imported_api.md

# Step 3：生成 pytest
./generate.sh templates/imported_api.md
./run_pytest.sh output/imported_api.py -v
```

细则：`api-skills/执行/references/openapi_pipeline.md` · 边界补充：`boundary_and_prd_supplement.md`

---

## 冒烟捷径（Day-1）

用户明确「直出/冒烟」时：

```bash
./generate.sh --import-openapi openapi.yaml --smoke-only \
  --auth-profile templates/auth_profiles/generic_rest.yaml \
  -o output/imported_smoke.md
./generate.sh output/imported_smoke.md
```

细则：`api-skills/执行/references/openapi_smoke_mode.md`

---

## 底层 import（`run_spec.py --import-openapi`）

```bash
python3 codegen/run_spec.py --import-openapi /path/to/openapi.json -o output/imported_spec.md
python3 codegen/run_spec.py --import-openapi http://your-server:8080/openapi.json \
  --base-url http://your-server:5001 -o output/imported_spec.md
```

| 能力 | 说明 |
|------|------|
| **$ref 解析** | 自动展开组件引用 |
| **security 识别** | Bearer 登录 + auth profile |
| **链式场景** | 列表 GET → capture id → 详情/操作 |
| **边界 E 层** | 标准流水线由 `openapi_to_cases.py` 生成（非 smoke 模式） |

生成后检查 YAML frontmatter 的 `base_url`、cases/scenarios，再 `./generate.sh`。

---

## HAR → API 用例（补充）

```bash
python3 codegen/har_to_cases.py -i capture.har -o output/cases_from_har.json \
  --base-url http://your-server:5001 \
  --auth-profile templates/auth_profiles/generic_rest.yaml
python3 codegen/testcase_to_api_spec.py -i output/cases_from_har.json -o templates/imported_api.md
```

---

## 限制

- OpenAPI 3.0 / Swagger 2.0
- 复杂 OAuth2 授权码需手动配置 auth profile
- multipart 文件上传需手写 spec 补充
