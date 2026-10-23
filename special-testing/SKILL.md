---
name: special-testing
description: Covers performance (e.g. Locust) and other non-functional testing with templates and generators. Use for perf or specialized test types beyond functional flows.
---

# 专项测试 Skill

> **日常压测优先** `@load-testing/执行/SKILL.md`（k6 / JMeter / 报告四阶段）。  
> 本 Skill 侧重 **Locust 冒烟**（`./generate.sh templates/perf_test.md`）、**视觉回归**（`templates/visual_regression.md`）及专项 roadmap。  
> 能力状态与 README「技能目录」表一致：**可执行** vs **规划中** 见下文各节标题。

## 用途

功能测试之外，还有性能压测等专项测试。这个 skill 覆盖这些细分领域。

## 已实现：性能压测

性能压测已经集成到生成器中，支持生成 **Locust**、**k6**、**JMeter** 脚本。同一份 `perf_test` spec 通过 `engine` 字段选择引擎（**默认 `k6`**；Locust 冒烟见 `templates/perf_test.md` 已显式 `engine: locust`）。

### 方式一：用内置模板

```bash
# Locust（显式 engine: locust，见 templates/perf_test.md）
./generate.sh templates/perf_test.md
cd output && locust -f perf_test.py --headless -u 10 -r 2 -t 30s

# k6（codegen 默认；或 templates/perf_test_k6.md）
./generate.sh templates/perf_test_k6.md
cd output && k6 run perf_test_k6.js

# JMeter
./generate.sh templates/perf_test_jmeter.md
jmeter -n -t output/perf_test_jmeter.jmx -l output/result.jtl -e -o output/jmeter-report
```

模板里预设了 3 个接口的压测配置（并发数、压测时长、响应时间断言），改改 `base_url` 和接口路径就能用。

### 方式二：自己写 spec

```markdown
---
kind: perf_test
engine: k6          # locust | k6 | jmeter（省略则 k6）
base_url: http://your-server:5001
concurrent: 10
duration: 60
ramp_up: 10
endpoints:
  - name: 获取用户列表
    method: GET
    path: /api/users
    weight: 5
    expect_status: 200
    max_response_ms: 500
  - name: 创建用户
    method: POST
    path: /api/users
    weight: 2
    json_body:
      name: "压测用户"
      email: "perf@test.com"
    expect_status: 201
    max_response_ms: 1000
---

# 性能测试 spec
```

```bash
./generate.sh my_perf_spec.md
# locust → output/my_perf_spec.py
# k6     → output/my_perf_spec.js
# jmeter → output/my_perf_spec.jmx
```

### 生成的脚本包含什么

- 并发用户数配置（`concurrent` / VU / 线程数）
- 爬坡与持续时间（`ramp_up` + `duration`）
- 响应时间断言（超过 `max_response_ms` 标记失败）
- 状态码断言（`expect_status`）
- 权重配置（`weight` 控制接口访问频率；JMeter 通过 Random Controller 按权重展开）

### Locust Web UI

```bash
cd output && locust -f my_perf_spec.py
# 浏览器打开 http://localhost:8089
```

在 Web UI 里可以动态调整并发数、压测时长，实时查看 QPS、响应时间分布、失败率。

## 已实现：视觉回归测试

视觉回归测试用于检测 UI 页面的视觉变化。每次运行截图并与基线对比，差异超过阈值则判定失败。

### 方式一：用内置模板

```bash
./generate.sh templates/visual_regression.md
cd output && pytest visual_regression.py --update-snapshots -v  # 首次：生成基线
cd output && pytest visual_regression.py -v                      # 后续：对比基线
```

### 方式二：自己写 spec

```markdown
---
kind: visual_regression
base_url: http://localhost:5566
viewport:
  width: 1280
  height: 720
threshold: 0.2
max_diff_pixels: 100
pages:
  - name: 登录页
    path: /login
    wait_ms: 2000
  - name: 仪表盘
    path: /dashboard
    wait_ms: 3000
    # 可选：截图前登录
    actions:
      - action: fill
        l1_label: "用户名"
        value: "admin"
      - action: fill
        l1_label: "密码"
        value: "123456"
      - action: click
        l1_role: button
        l1_name: "登录"
      - action: wait_timeout_ms
        ms: 1000
---

# 视觉回归测试
```

### 工作流程

1. **首次运行**：`pytest --update-snapshots` 生成基线截图，保存在 `__snapshots__/` 目录
2. **后续运行**：`pytest` 截图并与基线对比，差异超过 `threshold` 或 `max_diff_pixels` 则失败
3. **确认改版**：UI 改版后，重新运行 `pytest --update-snapshots` 更新基线

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `threshold` | 0.2 | 像素差异阈值（0.0-1.0），越小越严格 |
| `max_diff_pixels` | 100 | 允许的最大差异像素数 |
| `wait_ms` | 2000 | 截图前等待时间（毫秒） |

## 规划中（SKILL 文档，未实现）

以下功能目前只有 SKILL 文档，需要 AI 编辑器辅助使用，不能一行命令跑：

### UI 规范审查

检查页面是否符合设计规范（字体、颜色、间距、组件尺寸）。需要在 AI 编辑器 Chat 里：

```
@special-testing/SKILL.md

帮我检查 http://your-server:5001/products 的页面是否符合设计规范。
设计规范：主色 #1890ff，字体 PingFang SC，间距 8px 倍数。
```

### 安全扫描

检查认证绕过、越权、注入、XSS 等安全问题。需要在 AI 编辑器 Chat 里：

```
@special-testing/SKILL.md

帮我生成安全测试用例，覆盖 auth、injection、xss。
接口文档在 openapi.json。
```

### 代码质量门禁

检查代码规范、硬编码密码、SQL 拼接等问题。需要在 AI 编辑器 Chat 里：

```
@special-testing/SKILL.md

帮我检查 src/ 目录下的 Python 代码质量。
重点检查：flake8 规范、类型注解、循环复杂度。
```

## 注意事项

1. **性能测试需要独立环境**：不要在开发环境压测，会影响其他人
2. **安全扫描要谨慎**：注入类扫描可能影响数据，只在测试环境执行
3. **UI 规范需要设计稿**：没有设计规范就无法检查一致性，先和产品确认规范
4. **代码质量是建议不是阻断**：检查结果作为参考，不强制阻断提交流程
