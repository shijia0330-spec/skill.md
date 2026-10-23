---
name: api-self-healing
description: API测试自愈 — 运行时 HealingSession 自动重试（401/5xx/超时/断连）+ pytest 脚本补丁 Healer。契约漂移后最小改动复跑。
---

# API 脚本跑挂了 — 自愈与 Healer

两层能力：**运行时重试**（`codegen/api_lib/http_client.py` · `HealingSession`）+ **脚本补丁 Healer**（契约漂移后最小改动复跑）。

服务端逻辑本身错了，别指望这里「修到绿」。

---

## 1. 运行时重试（HealingSession · 已实现）

默认 `max_retries=3`（每种故障最多额外重试 **3** 次）。

实现见 `HealingSession.request()`；spec 可通过 `use_healing: false` 关闭。

| 故障类型 | 策略 | 重试次数 | 延迟 / 行为 |
|----------|------|----------|-------------|
| **401 Unauthorized** | 调用 `_login_fn` 重新登录 | 最多 **3** 次 | 重登后立即重试 |
| **500/502/503/504** | 固定间隔重试 | 最多 **3** 次 | `0.5s × (attempt+1)` |
| **超时** | 递增 timeout 后重试 | 最多 **3** 次 | timeout 每次 +10s（上限 120s） |
| **连接失败** | 重试 | 最多 **3** 次 | `0.5s × (attempt+1)` |
| **429 Rate Limit** | 读取 `Retry-After` 或线性退避 | 最多 **3** 次 | 与 `max_retries` 一致 |

**前提（401 刷新）**：session 由 `create_api_session` 创建且 spec 配了 `auth: bearer_login`；`no_auth` case 不会自动刷新。

```
第1次 GET /api/auth/profile → 401
     ↓ 自愈：POST /api/auth/login → 新 token 写入 Header + 变量池
第2次 GET /api/auth/profile → 200 ✅
```

### 什么时候报 Bug？

| 情况 | 处理 |
|------|------|
| 重试次数用尽仍失败 | → 报 Bug（defect-analysis / bug-reporter） |
| 400 参数错误 | → 报 Bug（重试无意义） |
| 业务断言失败 | → 报 Bug |
| token_refresh 后最终通过 | → 可标 `healed: true`，视团队约定是否报 Bug |

### 与 spec 的关系

```yaml
# api_pytest spec（默认已开启）
use_healing: true   # false 时用普通 requests.Session

auth:
  type: bearer_login
  login_path: /api/auth/login
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
```

`HealingSession` 的 `max_retries` 目前代码默认 **3**，尚未从 spec YAML 读取。

---

## 2. 脚本补丁 Healer（契约漂移 · 最小改动）

面向 **pytest + HTTP 客户端**。思路：**先看失败像哪一类，再最小改动打补丁，最后必须复跑证明有效**。

| 现象大类 | 多半是什么 | 常见改法 |
|----------|------------|----------|
| 响应 JSON 对不上 | 字段改了名、嵌套变了 | 改断言路径或 `expect_json_subset` |
| 401 / 403 | token、Header、权限 | 刷新 token、核对 `generic_rest.yaml` |
| 404 | 路径、版本前缀 | 改 path（秒杀 API 以 `/api/` 为准） |
| 200 但业务码不对 | 产品改了规则 | 更新期望值 |
| 422 | 请求体不符合校验 | 改造数、边界值 |
| 多步流程断了 | 接口顺序变了 | 调整 `scenarios[]` 或变量池 |

对不上的就不要硬自动修复，输出结论让人接手。

### Step 1：捕获失败详情

pytest 失败时查看：

- `output/reports/failure_analysis.json`
- 终端 longrepr 中的 status / response body 节选
- 必要时在 fixture 中记录 request/response（脱敏）

### Step 2～3：归类、补丁、复跑

场景模板见 **`01_Healer修复提示模板.md`**：

| 章节 | 场景 |
|------|------|
| 一、契约漂移 | JSON 字段/结构变化 |
| 二、认证问题 | 401/403 |
| 三、路由变更 | 404/重定向 |
| 四、断言失败 | 业务规则变化 |
| 五、数据约束 | 422 |
| 六、业务流程 | 多步顺序 |

复跑命令（包根目录）：

```bash
./run_pytest.sh output/seckill_api_smoke.py -v
```

---

## 3. 每次建议留下什么

- **看见了啥**：错误类型、堆栈一两行、请求响应节选（脱敏）
- **改了啥**：假设是什么、动了哪几行
- **怎么验证**：复跑命令、结果

---

## 4. 几条底线

- 改动越小越好：优先改 path/断言，不改框架
- 补丁必须能再跑通；日志里**别落真实密钥**
- **同一用例连续失败超过 3 次** → 转人工
- Healer 不负责重写整个 spec / 框架

---

## 5. 单元测试

`codegen/test_api_lib.py` 中 `test_healing_session_401_*` 覆盖：401 刷新成功、无 `_login_fn` 不重试、重试用尽仍 401。

```bash
python3 -m pytest codegen/test_api_lib.py -q -k healing
```
