# 方案准出 ↔ generate.sh ↔ pytest 对齐

方案 §7 准出、§4 方法中的自动化表述，须与本 monorepo 工具链 **一一可执行**。

---

## 1. 映射表（财务）

| 方案准出条（示例） | spec 模板 | 生成命令 | 验收命令（无后端） | 验收命令（有后端） |
|-------------------|-----------|----------|-------------------|-------------------|
| 认证冒烟全绿 | `templates/api_auth.md` | `./generate.sh templates/api_auth.md` | `cd output && python3 -m pytest _api_auth.py --collect-only -q` | `./run_pytest.sh output/_api_auth.py -v` |
| API 冒烟 | `templates/api_smoke.md` | `./generate.sh templates/api_smoke.md` | collect-only ≥2 tests | `./run_pytest.sh output/_api_smoke.py -v` |
| 通用冒烟 | `templates/api_smoke.md` | `./generate.sh templates/api_smoke.md` | collect-only | `./run_pytest.sh output/api_smoke.py -v` |
| OpenAPI 对齐 | 同上 + openapi | `./generate.sh templates/api_smoke.md --import-openapi path/to/openapi.yaml` | collect-only | 同上 |

环境变量：`TEST_USERNAME=admin`、`TEST_PASSWORD=123456`（见 `.env.example`）。

---

## 2. 方案中怎么写（§4 / §7）

**推荐句式**（可观测）：

```markdown
- [ ] 自动化冒烟：`./run_pytest.sh output/_api_smoke.py -v` 全绿（有 REST 测试环境 时）
- [ ] 或链路验收：`python3 -m pytest output/_api_smoke.py --collect-only -q` 预期 ≥ N tests（无后端时）
```

**禁止**：「自动化已通过」无命令、无产物路径。

---

## 3. 与 testcase-skills 评审对齐

| 层级 | 对齐点 |
|------|--------|
| 方案准出 | 上表命令 |
| 用例评审 | `testcase-skills/评审` + `api-skills/执行/references/status_code_assertions.md` |
| 计划 W1 退出 | 常写 collect-only 或 smoke 全绿 |

---

## 4. 计划里程碑建议

| 里程碑 | 自动化目标 |
|--------|------------|
| W1 | `_api_smoke` 或 `_api_auth` collect-only OK |
| W4 | 有后端时 smoke `-v` 全绿 |

---

## 5. 方案 Step 4 自检

- [ ] 每个自动化准出条有 template 名 + 命令  
- [ ] 无后端场景写了 collect-only 替代  
- [ ] 未引用不存在的 `templates/*.md`

---

## 6. REST 测试环境

`REST 测试环境` 需单独部署；无后端时 START_HERE 路径 B 仍可用 collect-only 验收生成链路。
