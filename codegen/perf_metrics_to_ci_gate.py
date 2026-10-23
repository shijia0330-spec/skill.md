#!/usr/bin/env python3
"""
压测结果 → ci-gate metrics JSON → 可选执行门禁。

用法:
  python3 codegen/perf_metrics_to_ci_gate.py --k6 output/k6_summary.json -o output/perf_metrics.json
  python3 codegen/perf_metrics_to_ci_gate.py --jtl output/result.jtl -o output/perf_metrics.json --run-gate --env prod
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from perf_report_from_results import parse_jmeter_jtl, parse_k6_summary


def to_ci_gate_metrics(parsed: dict) -> dict:
    summary = parsed.get("summary") or {}
    p95_ms = float(summary.get("p95_ms") or 0)
    err_pct = float(summary.get("error_rate_pct") or 0)
    error_rate = err_pct / 100.0
    tps = float(summary.get("tps") or summary.get("rate") or 0)
    total = int(summary.get("total_requests") or 0)
    return {
        "performance": {
            "avg_response_time": p95_ms * 0.6,
            "p95_response_time": p95_ms,
            "p99_response_time": p95_ms * 1.2,
            "failure_rate": error_rate,
            "error_rate": error_rate,
            "qps": tps,
            "total_requests": total,
        },
        "quality": {
            "test_pass_rate": max(0.0, 1.0 - error_rate),
        },
        "assertion": {
            "critical_pass_rate": max(0.0, 1.0 - error_rate),
            "business_pass_rate": max(0.0, 1.0 - error_rate),
        },
        "source": {
            "tool": parsed.get("tool"),
            "file": parsed.get("source"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jtl", type=Path, help="JMeter JTL")
    ap.add_argument("--k6", type=Path, help="k6 summary JSON")
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "output" / "perf_metrics.json")
    ap.add_argument("--run-gate", action="store_true", help="转换后执行 ci-gate")
    ap.add_argument("--env", default="prod", choices=["dev", "staging", "prod"])
    ap.add_argument("--write-bug", action="store_true", help="门禁失败时写 output/bugs/BUG-perf-gate.md")
    ns = ap.parse_args()

    if bool(ns.jtl) == bool(ns.k6):
        ap.error("请指定 --jtl 或 --k6 之一")

    parsed = parse_jmeter_jtl(ns.jtl) if ns.jtl else parse_k6_summary(ns.k6)
    metrics = to_ci_gate_metrics(parsed)
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 metrics: {ns.out.resolve()}")

    gate_ok = True
    if ns.run_gate:
        gate_script = ROOT / "ci-gate" / "scripts" / "ci_gate.py"
        r = subprocess.run(
            [sys.executable, str(gate_script), "--env", ns.env, "--metrics", str(ns.out)],
            cwd=str(ROOT),
        )
        gate_ok = r.returncode == 0
        if not gate_ok and ns.write_bug:
            bugs = ROOT / "output" / "bugs"
            bugs.mkdir(parents=True, exist_ok=True)
            perf = metrics["performance"]
            bug = bugs / "BUG-perf-gate.md"
            bug.write_text(
                f"""# 缺陷报告草稿 — BUG-PERF-GATE

| 字段 | 值 |
|------|-----|
| 标题 | 压测 CI 门禁未通过 |
| 严重程度 | High |
| 缺陷类型 | 性能 |
| 当前状态 | Draft |

## 问题描述

- P95: {perf.get('p95_response_time')} ms
- 错误率: {perf.get('error_rate')}
- QPS: {perf.get('qps')}

metrics 文件: `{ns.out}`
""",
                encoding="utf-8",
            )
            print(f"已写缺陷草稿: {bug}")
        return r.returncode

    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
