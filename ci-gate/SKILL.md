---
name: ci-gate
description: CI 门禁引擎 — 可执行的四维度质量关卡（性能/安全/代码质量/断言），支持自动回滚。
---

# CI 门禁引擎

可执行的 CI 门禁检查系统，四维度质量关卡 + 自动回滚。

---

## 做 / 不做

| 做 | 不做 |
|----|------|
| 四维度阈值检查（性能/安全/代码质量/断言） | 执行测试（走 api-skills） |
| 环境差异化配置（开发/测试/生产） | 修代码（走开发） |
| 自动回滚 | |

---

## 快速使用

### 命令行

```bash
cd ci-gate/scripts

# 生产环境检查
python3 ci_gate.py --env prod --metrics metrics.json

# 带自动回滚
python3 ci_gate.py --env prod --auto-rollback

# 指定输出格式
python3 ci_gate.py --env staging --output markdown
```

### Python 调用

```python
from quality_gate import create_checker

checker = create_checker("prod", auto_rollback=True)

metrics = {
    "performance": {"avg_response_time": 180, "p95_response_time": 450},
    "security": {"critical_vulnerabilities": 0},
    "quality": {"code_coverage": 0.92},
    "assertion": {"critical_pass_rate": 1.0},
}

result = checker.check(metrics, "生产环境门禁检查")
print(result.report)
```

---

## 四维度阈值

### 性能维度

| 参数 | 开发环境 | 测试环境 | 生产环境 |
|------|----------|----------|----------|
| 平均响应时间 | ≤ 500ms | ≤ 300ms | ≤ 200ms |
| P95 响应时间 | ≤ 1000ms | ≤ 800ms | ≤ 500ms |
| P99 响应时间 | ≤ 2000ms | ≤ 1500ms | ≤ 1000ms |
| 失败率 | ≤ 5% | ≤ 2% | ≤ 1% |
| 错误率 | ≤ 3% | ≤ 1% | ≤ 0.5% |
| QPS | ≥ 50 | ≥ 100 | ≥ 500 |

### 安全维度

| 参数 | 开发环境 | 测试环境 | 生产环境 |
|------|----------|----------|----------|
| 严重漏洞 | ≤ 2 | ≤ 0 | 0 |
| 高危漏洞 | ≤ 5 | ≤ 2 | 0 |
| 中危漏洞 | ≤ 10 | ≤ 5 | ≤ 5 |

### 代码质量维度

| 参数 | 开发环境 | 测试环境 | 生产环境 |
|------|----------|----------|----------|
| 代码覆盖率 | ≥ 60% | ≥ 80% | ≥ 90% |
| 代码异味 | ≤ 20 | ≤ 10 | ≤ 5 |
| 测试通过率 | ≥ 80% | ≥ 95% | ≥ 98% |

---

## 文件结构

```
ci-gate/
├── SKILL.md
├── scripts/
│   ├── quality_gate.py   # 门禁检查器
│   ├── rollback.py       # 自动回滚
│   └── ci_gate.py        # 入口脚本
├── references/
│   └── ci_gate.md        # CI 门禁参考
└── config/
    └── environments.json # 环境配置
```

---

## 输出格式

| 格式 | 说明 |
|------|------|
| text | 终端输出，适合 CI 日志 |
| HTML | 可视化报告，适合邮件发送 |
| Markdown | 适合贴到钉钉 |

---

## CI/CD 集成

### GitHub Actions

```yaml
- name: CI 门禁检查
  run: |
    cd ci-gate/scripts
    python3 ci_gate.py --env production --metrics results.json
```

### GitLab CI

```yaml
quality_gate:
  stage: deploy
  script:
    - cd ci-gate/scripts
    - python3 ci_gate.py --env production --auto-rollback
```
