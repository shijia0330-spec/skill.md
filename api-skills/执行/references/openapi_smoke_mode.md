# OpenAPI 冒烟模式（直出 spec / pytest）

**定位**：连通性验证、CI collect-only、Teaching Demo。**不能**作为版本准出唯一依据。

---

## 命令

```bash
# spec（仅 H 主路径，无 X 负例）
./generate.sh --import-openapi openapi.yaml \
  --base-url http://127.0.0.1:8080 \
  --auth-profile templates/auth_profiles/generic_rest.yaml \
  --smoke-only \
  -o output/imported_smoke.md

./generate.sh output/imported_smoke.md

# 或等价
python3 codegen/run_spec.py --import-openapi openapi.yaml --smoke-only -o output/imported_smoke.md
```

生成的 spec frontmatter 含 **`import_mode: smoke`**，正文有醒目说明。

---

## 冒烟模式包含什么

| 有 | 无 |
|----|-----|
| 每 operation 一条 H case | X 层 401/422 负例 |
| Bearer → 可配置 auth profile | 业务权限/多组织场景 |
| 链式 list→detail scenario | 评审过的 P0 断言 |
| 可选弱 `expect_json_subset` | 角色权限矩阵 |

---

## 何时升级到标准流水线

- 要上 **CI 准出** 或 **秒杀财务 P0**
- OpenAPI 里没有写清 403/业务错误码
- 需要 **scenarios** 串联 login → 带 token 访问

→ 改走 `references/openapi_pipeline.md`（`openapi_to_cases.py` → 评审 → `testcase_to_api_spec.py`）。
