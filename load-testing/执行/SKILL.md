---
name: load-execution
description: 压测脚本生成与执行 — 默认 k6 (.js)；可选 JMeter (.jmx)。对齐 seckill_finance_system openapi。
---

# 压测执行

根据规划生成可执行的压测脚本，并执行压测。

---

## 默认引擎：k6

**除非用户明确要求 JMeter，否则一律生成 k6 `.js` 脚本。**

| 理由 | 说明 |
|------|------|
| CI 友好 | `k6 run` + thresholds 可直接当门禁 |
| 与包内 openapi 对齐 | 参考 `references/k6-template.js` |
| 快速冒烟 | Locust 走 `generate.sh templates/perf_test.md`（codegen 路径） |

---

## 快速使用

```text
@load-testing/执行/SKILL.md

针对 seckill_finance_system 生成 k6 压测脚本：
- BASE_URL=http://your-server:5001
- 阶梯 10→50→200，总时长约 8 分钟
- 接口：GET /api/health、POST /api/auth/login、GET /api/products、GET /api/auth/profile
- 输出 output/seckill_load.js
```

生成后执行：

```bash
k6 run output/seckill_load.js
# 或
BASE_URL=http://your-server:5001 TEST_USERNAME=admin TEST_PASSWORD=admin123 k6 run output/seckill_load.js
```

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| **默认**生成 k6 .js 脚本 | 分析压测结果（走报告/SKILL.md） |
| 用户指定时生成 JMeter .jmx | 规划压测场景（走规划/SKILL.md） |
| 提供执行命令 + 冒烟步骤 | |

---

## seckill_finance_system 接口约定

生成脚本时 **须** 使用下列路径（勿用旧版 `/api/login`、`/api/users`）：

| 场景 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 健康检查 | GET | `/` 或 `/api/health` | 无需登录；Docker 5001 常用 `/`（`HEALTH_PATH` 环境变量） |
| 登录 | POST | `/api/auth/login` | body: `{username, password}`；token 字段 `token` |
| 商品列表 | GET | `/api/products` | 匿名可访问 |
| 用户信息 | GET | `/api/auth/profile` | Header: `Authorization: Bearer <token>` |
| 销售订单 | POST | `/api/sales/orders` | 需登录；写压场景再用 |

**参考模板**：
- k6：`load-testing/references/k6-template.js` → 复制到 `output/seckill_load.js`
- JMeter：`./generate_jmeter.sh` → `output/seckill_load.jmx`（模板 `load-testing/references/seckill_load.jmx`）

**Locust 冒烟（非 k6）**：`./generate.sh templates/perf_test.md` → `output/perf_test.py`。

---

## 引擎选择

| 维度 | k6（默认） | JMeter | Locust |
|------|------------|--------|--------|
| 脚本格式 | .js | .jmx (XML) | .py |
| CI/CD | 原生 thresholds | 需插件/HTML 报告 | 原生 headless |
| 何时用 | 未指定引擎、现代流水线 | 用户明确要 JMeter / 已有 jmx 资产 | 快速冒烟（codegen 路径） |
| 生成方式 | 手动复制模板改 | `./generate.sh templates/jmeter_test.md` | `./generate.sh templates/perf_test.md` |
| 数据源 | 环境变量 | CSV Data Set Config | 代码内硬编码 |

---

## k6 脚本生成（默认）

### 输出结构

以 `references/k6-template.js` 为起点，至少包含：

- `options.stages` 或 `options.scenarios`（并发模型）
- `options.thresholds`（p95、error_rate）
- `BASE_URL` / `TEST_USERNAME` / `TEST_PASSWORD` 环境变量
- `check()` 断言（状态码 + 关键 JSON 字段）
- 登录关联：`POST /api/auth/login` → 提取 `token` → 后续 Bearer

### 默认参数

| 参数 | 默认值 |
|------|--------|
| BASE_URL | `http://your-server:5001`（Docker）；本地可 `5000` |
| HTTP 超时 | k6 默认；必要时 `http.setResponseCallback` |
| 冒烟 stages | 1 VU，30s |
| 负载 stages | 10→50→200，保持 5min，下降 30s |
| 阈值 | p(95)<500ms，error_rate<1% |

### 执行命令

```bash
k6 run output/压测脚本.js

BASE_URL=http://your-server:5001 k6 run output/压测脚本.js

k6 run --out json=output/k6-results.json output/压测脚本.js
```

---

## JMeter 脚本生成（仅用户指定时）

### 一键生成与执行

```bash
./generate_jmeter.sh              # → output/seckill_load.jmx
./run_jmeter.sh                   # 冒烟：2 线程 / 10 秒
./run_jmeter.sh --full            # 正式：10 线程 / 60 秒

# 自定义
TEST_BASE_URL=http://your-server:5001 THREADS=50 DURATION=300 ./run_jmeter.sh
```

### 输出结构

```
Test Plan
├── HTTP Request Defaults (base_url, 超时)
├── CSV Data Set Config（从 data_factory 导出的 CSV 读取用户数据）
├── 线程组 (并发模型)
│   ├── HTTP Header Manager
│   ├── HTTP Request（路径对齐上表 openapi）
│   ├── JSON Extractor（token 来自 /api/auth/login）
│   └── 断言
└── 监听器
```

参考：
- 可运行模板：`load-testing/references/seckill_load.jmx`
- 结构说明：`load-testing/references/jmeter-template.md`
- spec 模板：`templates/jmeter_test.md`

### data_factory 衔接（多用户压测 · 完整链路）

**原则**：CSV 一行 = 一个虚拟用户；**并发线程/VU 数 = CSV 有效行数** 时，每线程/每 VU 取不同账号，避免单账号限流。

**密码约定**：CSV 导出 **明文 `password`**（`extra_columns`）；DB 存 `password_hash: hash_password("Test123!")`。登录 body 用 `${password}`，**勿用 `password_hash`**。

#### 1. 造数并导出 CSV

```bash
python3 codegen/run_spec.py templates/data_factory.md -o output/data_factory.py
cd output && python3 data_factory.py
# 产出: output/users.csv（username, password）
# 数据行数 N = wc -l users.csv - 1（减去表头）
wc -l output/users.csv
cd ..
```

#### 2. 生成压测脚本（读同一 CSV）

**JMeter：**

```bash
python3 codegen/run_spec.py templates/jmeter_test.md -o output/api_load.jmx
# data_source: variables [username, password], ignore_first_line: true, recycle: false
```

**k6（推荐 codegen，勿手写 papaparse）：**

```bash
./generate.sh templates/perf_test_k6_multiuser.md
# → output/perf_test_k6_multiuser.js（每 VU 独立登录 + Bearer）
```

#### 3. 压测（线程/VU 数 = N）

```bash
# JMeter — 多用户勿跑 fetch_perf_token.py（每线程 CSV 独立登录）
jmeter -n -t output/api_load.jmx -JHOST=127.0.0.1 -JPORT=5001 \
  -JTHREADS=N -JDURATION=60 \
  -l output/results.jtl -e -o output/jmeter-report/

# k6
k6 run -e BASE_URL=http://127.0.0.1:5001 output/perf_test_k6_multiuser.js
```

| 项 | 约定 |
|----|------|
| CSV 列 | `username, password`（顺序与 `variableNames` 一致） |
| CSV 行数 | N（不含表头） |
| JMeter 线程 / k6 concurrent | **N**（或 ≤N） |
| ignoreFirstLine | **true**（CSV 有表头） |
| Recycle | **false**（每线程一账号） |
| Token | 多用户：JMX/k6 内 CSV 驱动 login；**勿**预灌单 Token |

#### 4. 清理

```bash
cd output && python3 data_factory.py --cleanup
```

**关键点：**
- `data_factory.users.count` ≥ 规划目标并发
- `csv_export.fields` + `extra_columns` 列名与 `data_source.variables` 一致
- 单用户冒烟仍用 `k6-template.js` + `fetch_perf_token.py`（见下节 Token）

### 执行命令（单用户冒烟）

```bash
./generate_jmeter.sh
./run_jmeter.sh

# 或手动
jmeter -n -t output/seckill_load.jmx -JHOST=127.0.0.1 -JPORT=5001 \
  -l output/jmeter-results.jtl -e -o output/jmeter-report/
```

---

## 工作流

1. **读取规划** — 从 `load-testing/规划/SKILL.md` 获取场景 + 并发
2. **选择引擎** — **默认 k6**；仅当用户说 JMeter 时才出 .jmx
3. **复制并对齐模板** — 基于 `references/k6-template.js` 改 stages 与接口权重
4. **冒烟** — `k6 run --vus 1 --duration 30s output/脚本.js`
5. **正式压测** — 全量 stages
6. **报告** — `load-testing/报告/SKILL.md`

---

## 质量门槛

- [OK] 默认产出 k6（除非明确要求 JMeter）
- [OK] 接口路径符合 openapi（见上表）
- [OK] stages + thresholds
- [OK] 登录 token 关联（需鉴权场景）
- [OK] 执行命令与 BASE_URL 说明

---

## Token（执行前必做 · 需鉴权场景）

秒杀 API 使用 **REST 登录**（非 UI 验证码）。压测前须刷新 Token 并写入环境文件。

```bash
# 包根目录：登录 + 探针 GET /api/auth/profile
python3 codegen/fetch_perf_token.py --output-env output/.perf_env

# 加载后执行 k6（Windows PowerShell 示例）
Get-Content output/.perf_env | ForEach-Object {
  if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
k6 run -e BASE_URL=http://your-server:5001 \
  -e TEST_USERNAME=admin -e TEST_PASSWORD=admin123 \
  -e PERF_ACCESS_TOKEN=$env:PERF_ACCESS_TOKEN \
  output/seckill_load.js
```

| 项 | 说明 |
|----|------|
| 脚本 | `codegen/fetch_perf_token.py` |
| 产出 | `output/.perf_env`（`PERF_ACCESS_TOKEN` 等） |
| 探针 | 登录后对 `/api/auth/profile` 校验，失败则重登 |
| k6 | **须显式 `-e`** 传入 Token（勿假设 shell 继承即可） |
| JMeter | `python3 codegen/run_jmeter_perf.py`（内部 refresh + `-J` 传参） |

> 每次正式压测前建议重新执行 `fetch_perf_token.py`；勿使用未探针的旧 Token。

---

## HAR → 压测（录制回放）

从浏览器 DevTools 导出 HAR，一键生成 spec + 脚本 + Token + 执行：

```powershell
# 包根目录
powershell -File run_perf_from_har.ps1 -Har capture.har -Engine both -Smoke `
  -AuthProfile templates/auth_profiles/generic_rest.yaml
```

| 步骤 | 命令 / 产出 |
|------|-------------|
| HAR → spec | `codegen/har_to_perf.py` → `templates/har_perf_k6.md` |
| spec → 脚本 | `run_spec.py` → `output/har_perf_k6.js` / `.jmx` |
| Token 探针 | `codegen/fetch_perf_token.py` → `output/.perf_env` |
| k6 执行 | `k6 run -e PERF_ACCESS_TOKEN=... output/har_perf_k6.js` |
| JMeter 执行 | `python3 codegen/run_jmeter_perf.py --skip-token` |
| 无 k6/JMeter | `python3 codegen/perf_smoke_validate.py -i capture.har` |

**codegen 引擎**（声明式，非 HAR）：

```bash
./generate.sh templates/perf_test_k6.md              # 单用户 k6
./generate.sh templates/perf_test_k6_multiuser.md    # 多用户 k6（衔接 data_factory CSV）
./generate.sh templates/perf_test_jmeter.md          # 单 Token JMeter
./generate.sh templates/jmeter_test.md             # 多用户 JMeter（衔接 data_factory CSV）
./generate.sh templates/perf_test.md                 # Locust .py（快速冒烟）
```

**HAR → 用例 JSON**（接口测试侧）：

```bash
python3 codegen/har_to_cases.py -i capture.har -o output/cases_from_har.json \
  --base-url http://your-server:5001 --auth-profile templates/auth_profiles/generic_rest.yaml
```

报告：`load-testing/报告/SKILL.md` · `codegen/perf_report_from_results.py`
