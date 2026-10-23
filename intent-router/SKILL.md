---
name: intent-router
description: Routes ambiguous user requests to API, UI, mobile, or testcase skill paths using structured intent output. Use as entry dispatch before picking a workflow.
---

# 意图路由（入口分发）

**什么时候用**：用户一句话进来，还没说清楚要用哪个技能包时，先用这份约定判断「大概该派哪条线」，避免全场瞎猜。

**它不干什么**：不负责写用例、跑脚本、修代码，只做「往哪送」。

---

## 1. 建议给下游的机器可读结果

对接自动化或编排时，可以用 JSON 表达结论（字段名和 `mapping.yaml` 里保持一致）：

```json
{
  "intent_tag": "api_automation",
  "default_skill": "api-skills/执行",
  "skill_paths": ["api-skills"],
  "notes": "用户要做接口方面的自动化，默认从执行模块进"
}
```

`intent_tag`、`default_skill`、`skill_paths` 的含义见仓库里的 `intent-router/mapping.yaml`，不要自己发明一套键名。

---

## 2. 用户常挂在嘴边的说法 → 往哪条技能线想

下面不是穷举，而是平时对接时**最常遇见的几类说法**，方便新人对上号：

| 用户大概在说什么 | 一般会落到 |
|------------------|------------|
| 测试方案、测试计划、PRD+技术文档出方案 | `testplan-skills`，默认 `testplan-skills/方案` 或先 `分析` |
| 方案评审、计划评审 | `testplan-skills/评审` |
| 写用例、铺场景、需求追溯到案例 | `testcase-skills`，多数情况默认先进 `testcase-skills/生成` |
| 测试范围、迭代怎么排、上线前要卡什么（轻量） | `testcase-skills/规划` |
| 用例评审、质量把关、抽检 | `testcase-skills/评审` |
| **声明式造数**（MySQL/CSV/pytest 铺底/`data_factory`） | `data-factory/执行` |
| **用例驱动造数设计**（评审后 SQL/shell/Python） | `testcase-data-generator` |
| 接口、Swagger/OpenAPI、REST、HTTP 自动化 | `api-skills`，默认 **`references/openapi_pipeline.md`** |
| Swagger 直出、冒烟导入、smoke-only | `api-skills/执行/references/openapi_smoke_mode.md` |
| 接口脚本挂了、跑红了想修 | `api-skills/自我修复` |
| Markdown 用例筛 UI / 三件套 / md_ui_filter / 用例+截图筛选 | `UI-skills/转化` |
| 页面、浏览器、E2E、Playwright | `UI-skills`，默认 **`references/ui_pipeline.md`** |
| UI 冒烟、单页直出 | `UI-skills/执行/references/ui_smoke_mode.md` |
| App、手机、真机/模拟器、Appium、移动端 E2E、`appium_pytest` 声明式 | `mobile-skills`，默认入口 `mobile-skills/执行` |
| Appium 跑完出报告 | `mobile-skills/报告` |
| 页面脚本失败、定位飘了要修 | `UI-skills/自我修复` |
| 手机脚本/Appium 挂了要修 | `mobile-skills/自我修复` |
| 记缺陷、缺陷统计、复盘材料 | `bug-reporter` |
| 进度、还剩多少事、当前在做什么 | `progress-reporter` |
| 需求建模、测什么不测什么、范围拆解 | `requirement-modeling` |
| **压测、k6、JMeter、性能测试** | `load-testing/执行`（报告 → `load-testing/报告`） |
| Locust 冒烟、`perf_test.md` 直出 | `special-testing`（亦可用 `load-testing`） |

听不清楚时，宁可多问一句「你是要改接口脚本还是改页面脚本？」，也不要硬猜。

---

## 3. 短语表（配置文件）

具体触发词写在 **`intent-router/mapping.yaml`** 里维护；可执行解析见 **`intent-router/resolve_intent.py`**（`codegen/test_intent_router_mapping.py` 回归 20+ 话术）。

- **`revision`**：这份表的格式版本，改结构时顺手改一下，免得老工具读错。
- **`rules`**：每一条里有 **`phrases`**（用户可能说的词）、**`skill_paths`**（会牵涉到的技能目录）、**`default_skill`**（默认先打开哪一个）。
- **匹配顺序**：文件是从上往下扫的，**先命中先生效**，所以常用的说法放在前面。

节选示例：

```yaml
revision: 12
ordering: top_down_short_circuit
rules:
  - tag: load_testing
    phrases:
      - 压测
      - 性能测试
    skill_paths:
      - load-testing/执行
    default_skill: load-testing/执行
  - tag: data_factory_codegen
    phrases:
      - 数据工厂
      - data_factory
    skill_paths:
      - data-factory/执行
    default_skill: data-factory/执行
```

---

## 4. 几种容易拧巴的情况

| 情况 | 怎么处理 |
|------|----------|
| 一句话里既有「页面」又有「接口」 | 看他动词落在谁身上（测页面流程还是测 HTTP）；仍说不清就问 |
| 说「自动化」但分不清浏览器还是 App | 测 **网站** 走 `UI-skills`；测 **安装包/小程序容器** 走 `mobile-skills`；两个都要就问清优先级 |
| 说「失败了」但带了日志 | 先分清是要**修脚本**（自愈）还是**记缺陷** |
| 用户已经 @ 了某个技能 | 按用户的来，这边只做依赖是否齐的提醒 |

---

## 5. 和别的文档怎么配合

- 自然语言先进这里，再分到各业务 SKILL。  
- 这里**不要**替下游写具体测试步骤。

---

## 6. 维护时注意

加新业务能力时，优先往 **`phrases`** 里加说法，不要随便改已有技能目录名；**规则顺序**就是优先级，动之前想清楚谁先匹配。
