# HTML 性能报告结构说明

生成 HTML 时以 `assets/performance-report-template.html` 为版式基准，**只替换占位内容**，不改动 CSS 与整体布局。

---

## 页面区块

| 区块 ID / 区域 | 填写内容 |
|----------------|----------|
| 标题区 | 项目或接口名 +「性能测试分析报告」 |
| meta 行 | 压测时间、环境、工具、场景摘要 |
| `#section-overview` | 测试目的、并发模型、持续时间、通过/不通过结论 |
| `#section-metrics` | 核心指标表（接口、并发、TPS、P95、错误率、结论列） |
| `#section-screenshots` | 截图 `<figure>`：图 + caption 说明 |
| `#section-bottleneck` | 分层瓶颈（资源 → 中间件 → DB → 应用），每条带依据 |
| `#section-suggestions` | 优化建议，分短期 / 中期 |
| `#section-summary` | 总结：能否上线、复测建议、风险遗留 |

---

## 表格规范

核心指标表至少包含列：

```
接口/事务 | 并发 | TPS/QPS | P95(ms) | 错误率 | 结论([OK]/[WARN]/[FAIL])
```

结论列规则：

- [OK] 达到目标或无明显瓶颈
- [WARN] 接近阈值或存在长尾
- [FAIL] 未达标或错误率过高

---

## 截图区规范

```html
<figure class="shot">
  <img src="相对路径或占位说明" alt="简短描述" />
  <figcaption>图1：JMeter 聚合报告 — 200 并发下 P95 480ms，错误率 0.2%</figcaption>
</figure>
```

对话内粘贴、无文件路径时：用灰色占位框 + 文字描述图内容。

---

## 输出约定

- 默认路径：`output/perf_report_<场景>_<YYYYMMDD>.html`
- 告知用户用浏览器打开；可打印或转 PDF
- 与 Markdown 版结论保持一致，HTML 侧重展示与归档
