# OpenAPI / 接口契约 — 方案层范围对齐

> 用例层细节见 `testcase-skills/生成/references/api_contract_supplement.md`。  
> 本文件约束 **测试方案** 如何把 OpenAPI 纳入 In-Scope 与接口测试深度。

---

## 1. 何时加载（方案 Step 3 前）

- 用户 `@` 了 `openapi.yaml` 或 `API接口文档.md`  
- 技术文档 §3 列出端点且 PRD 写「见接口文档」  
- 方案 §4 计划使用 `./generate.sh` 做 API 自动化  

---

## 2. 方案中要产出什么

| 产出 | 位置 |
|------|------|
| In-Scope API 清单 | 方案 §2.1 或 §2.3 追溯表 |
| 各模块「接口」策略深度 | 方案 §3.2（L0～L3） |
| OpenAPI 与 PRD 冲突 | 附录 A 待澄清 T-xx |
| 自动化模板建议 | 附录 D 或 `generate_sh_alignment.md` |

**不写**逐步 HTTP 用例（属 testcase-skills/生成）。

---

## 3. 端点 → 方案策略规则

对每个 In-Scope 端点至少标注：

| 维度 | 方案层写法 |
|------|------------|
| 鉴权 | 匿名 / JWT / admin → 安全列 ✓ |
| 成功路径 | 功能+接口 ≥ L1 |
| 4xx/5xx | 接口 ≥ L2（若 P0 模块） |
| PRD 无、契约有 | 追溯表标「契约存在」+ T-xx 或纳入 In-Scope |
| 冲突 | T-xx，不选边 |

---

## 4. 财务 OpenAPI 示例（节选）

| 端点 | 方案模块 | 接口深度 | 自动化模板 |
|------|----------|----------|------------|
| POST /api/auth/login | 认证 | L2 | `_api_auth.md` |
| GET /api/products | 商品 | L1 | `_api_smoke.md` |
| POST .../prepare-stock | Redis 预热 | L2 | （手工+集成） |
| POST /api//{aid}/{pid} | 下单 | L2 | 用例+可选 perf |

导入 OpenAPI 生成 spec（可选）：

```bash
./generate.sh templates/api_smoke.md --import-openapi REST 测试环境/openapi.yaml
```

生成物与方案准出对齐见 `generate_sh_alignment.md`。

---

## 5. 与 PRD 的关系（方案专用）

| 情况 | 方案处理 |
|------|----------|
| PRD 与契约一致 | §2.3 一行映射即可 |
| PRD 有、契约无 | 策略以 PRD 为准；备注「契约待同步」 |
| 契约有、PRD 无 | In-Scope 需产品确认或标 T-xx |
| 冲突 | 附录 A，阻塞准出条目标「待确认」 |

---

## 6. 方案 Step 3 自检

- [ ] 每个 P0 模块的关键 API 在 §2.3 或 §3.2 出现  
- [ ] 若承诺自动化准出，附录 D 有对应 template  
- [ ] 未编造 PRD/契约均未出现的端点
