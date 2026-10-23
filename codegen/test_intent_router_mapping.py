#!/usr/bin/env python3
"""intent-router/mapping.yaml 话术 → default_skill 回归（防规则漂移）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "intent-router"))

from resolve_intent import load_mapping, resolve_intent  # noqa: E402

# (用户话术, 期望 tag, 期望 default_skill 前缀或完整路径)
CASES: list[tuple[str, str, str]] = [
    ("从 PRD 写测试用例", "testcase_pipeline", "testcase-skills/生成"),
    ("用例评审走查", "testcase_review", "testcase-skills/评审"),
    ("测试方案与计划", "testplan_pipeline", "testplan-skills/方案"),
    ("需求建模测什么不测什么", "requirement_modeling", "requirement-modeling"),
    ("OpenAPI 导入做接口自动化", "api_automation", "api-skills/执行/references/openapi_pipeline"),
    ("Swagger 直出冒烟", "api_openapi_smoke", "openapi_smoke_mode"),
    ("接口步骤自愈", "api_heal", "api-skills/自我修复"),
    ("功能用例转自动化 md_ui_filter", "ui_md_conversion", "UI-skills/转化"),
    ("Playwright 流水线 E2E", "ui_automation", "UI-skills/执行/references/ui_pipeline"),
    ("UI 冒烟单页", "ui_smoke_direct", "ui_smoke_mode"),
    ("自然语言一句话操作页面", "ui_nl_one_shot", "UI-skills/nl-one-shot"),
    ("Appium 真机 Android", "mobile_automation", "mobile-skills/执行"),
    ("Appium 报错请自愈", "mobile_heal", "mobile-skills/自我修复"),
    ("k6 压测脚本", "load_testing", "load-testing/执行"),
    ("请生成 HTML 性能报告", "load_report", "load-testing/报告"),
    ("Locust perf_test 冒烟", "special_testing", "special-testing"),
    ("声明式造数 data_factory", "data_factory_codegen", "data-factory/执行"),
    ("记缺陷 bug 报告", "defect_intake", "bug-reporter"),
    ("推缺陷到禅道", "defect_sync", "defect-sync"),
    ("测试进度汇报", "progress_status", "progress-reporter"),
    ("E2E 页面自动化回归失败", "ui_heal", "UI-skills/自我修复"),
]


def main() -> int:
    mapping = load_mapping()
    rev = mapping.get("revision")
    errs: list[str] = []
    for text, tag, skill_needle in CASES:
        got = resolve_intent(text, mapping)
        if got is None:
            errs.append(f"无匹配: {text!r}")
            continue
        if got.get("intent_tag") != tag:
            errs.append(f"{text!r}: tag 期望 {tag!r} 实际 {got.get('intent_tag')!r}")
        skill = str(got.get("default_skill") or "")
        if skill_needle not in skill:
            errs.append(f"{text!r}: skill 期望含 {skill_needle!r} 实际 {skill!r}")
    if errs:
        print(f"intent-router 回归失败 ({len(errs)}/{len(CASES)}):", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"intent-router 回归通过: {len(CASES)} 条话术 (revision={rev})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
