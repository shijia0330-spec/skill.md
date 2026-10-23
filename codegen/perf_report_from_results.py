"""从 JMeter JTL / k6 summary JSON 生成 HTML 性能报告（填充 performance-report-template）。"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "load-testing" / "报告" / "assets" / "performance-report-template.html"

P95_MS_WARN = 800.0
ERROR_RATE_WARN = 0.01


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    return ordered[f] * (c - k) + ordered[c] * (k - f)


def _verdict(p95_ms: float, error_rate: float) -> tuple[str, str]:
    if error_rate > ERROR_RATE_WARN or p95_ms > P95_MS_WARN * 1.5:
        return "❌", "bad"
    if error_rate > 0 or p95_ms > P95_MS_WARN:
        return "⚠️", "warn"
    return "✅", "ok"


def parse_jmeter_jtl(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    rows_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with p.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "unknown").strip()
            rows_by_label[label].append(row)

    labels: list[dict[str, Any]] = []
    total_reqs = 0
    total_errors = 0
    all_elapsed: list[float] = []

    for label, rows in sorted(rows_by_label.items()):
        elapsed = [float(r.get("elapsed") or 0) for r in rows]
        all_elapsed.extend(elapsed)
        n = len(rows)
        errors = sum(1 for r in rows if str(r.get("success", "true")).lower() != "true")
        total_reqs += n
        total_errors += errors
        p95 = _percentile(elapsed, 95)
        avg = statistics.mean(elapsed) if elapsed else 0.0
        err_rate = errors / n if n else 0.0
        verdict, css = _verdict(p95, err_rate)
        labels.append(
            {
                "label": label,
                "samples": n,
                "avg_ms": round(avg, 1),
                "p95_ms": round(p95, 1),
                "error_rate": round(err_rate * 100, 2),
                "verdict": verdict,
                "verdict_class": css,
            }
        )

    duration_sec = 0.0
    ts_values = []
    for rows in rows_by_label.values():
        for r in rows:
            try:
                ts_values.append(int(r.get("timeStamp") or 0))
            except ValueError:
                pass
    if len(ts_values) >= 2:
        duration_sec = max(0.001, (max(ts_values) - min(ts_values)) / 1000.0)

    overall_p95 = _percentile(all_elapsed, 95)
    overall_err = total_errors / total_reqs if total_reqs else 0.0
    tps = total_reqs / duration_sec if duration_sec > 0 else 0.0

    return {
        "tool": "JMeter",
        "source": str(p),
        "labels": labels,
        "summary": {
            "total_requests": total_reqs,
            "total_errors": total_errors,
            "error_rate_pct": round(overall_err * 100, 2),
            "p95_ms": round(overall_p95, 1),
            "tps": round(tps, 2),
            "duration_sec": round(duration_sec, 1),
        },
    }


def parse_k6_summary(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    metrics = data.get("metrics") or data

    def _metric(name: str, key: str, default: float = 0.0) -> float:
        block = metrics.get(name) or {}
        if key in block:
            return float(block[key])
        values = block.get("values") or {}
        if key in values:
            return float(values[key])
        return default

    p95 = _metric("http_req_duration", "p(95)")
    if not p95:
        p95 = _metric("http_req_duration", "p95")
    avg = _metric("http_req_duration", "avg")
    reqs = int(_metric("http_reqs", "count"))
    rate = _metric("http_reqs", "rate")
    fail_rate = _metric("http_req_failed", "rate")
    duration = _metric("iteration_duration", "max") / 1000.0 if _metric("iteration_duration", "max") else 0.0

    verdict, css = _verdict(p95, fail_rate)
    label_row = {
        "label": data.get("root_group", {}).get("name") or "k6 汇总",
        "samples": reqs,
        "avg_ms": round(avg, 1),
        "p95_ms": round(p95, 1),
        "error_rate": round(fail_rate * 100, 2),
        "verdict": verdict,
        "verdict_class": css,
    }

    return {
        "tool": "k6",
        "source": str(p),
        "labels": [label_row],
        "summary": {
            "total_requests": reqs,
            "total_errors": int(reqs * fail_rate),
            "error_rate_pct": round(fail_rate * 100, 2),
            "p95_ms": round(p95, 1),
            "tps": round(rate, 2),
            "duration_sec": round(duration, 1),
        },
    }


def _metrics_table_html(labels: list[dict[str, Any]]) -> str:
    rows = []
    for item in labels:
        rows.append(
            f"<tr>"
            f"<td>{item['label']}</td>"
            f"<td>{item['samples']}</td>"
            f"<td>{item.get('tps', '—')}</td>"
            f"<td>{item['p95_ms']}</td>"
            f"<td>{item['error_rate']}%</td>"
            f"<td class=\"{item['verdict_class']}\">{item['verdict']}</td>"
            f"</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>接口/事务</th><th>样本数</th><th>TPS/QPS</th>"
        "<th>P95(ms)</th><th>错误率</th><th>结论</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_perf_report_html(
    metrics: dict[str, Any],
    *,
    title: str = "性能测试分析报告",
    scene: str = "",
    environment: str = "",
) -> str:
    if not TEMPLATE.is_file():
        raise FileNotFoundError(f"模板不存在: {TEMPLATE}")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    summary = metrics["summary"]
    tool = metrics.get("tool", "unknown")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    scene_text = scene or "压测场景"
    env_text = environment or "测试环境"
    meta = f"压测时间：{now} · 环境：{env_text} · 工具：{tool} · 数据源：{metrics.get('source', '')}"

    overall_ok = summary["error_rate_pct"] <= ERROR_RATE_WARN * 100 and summary["p95_ms"] <= P95_MS_WARN
    pass_text = "通过" if overall_ok else "未达标"

    overview = (
        f"<p><strong>场景</strong>：{scene_text}</p>"
        f"<p><strong>总请求</strong>：{summary['total_requests']} · "
        f"<strong>TPS</strong>：{summary['tps']} · "
        f"<strong>持续时间</strong>：约 {summary['duration_sec']}s</p>"
        f"<p><strong>整体 P95</strong>：{summary['p95_ms']}ms · "
        f"<strong>错误率</strong>：{summary['error_rate_pct']}% · "
        f"<strong>结论</strong>：<span class=\"{'ok' if overall_ok else 'bad'}\">{pass_text}</span></p>"
        f"<p>阈值参考：P95 ≤ {int(P95_MS_WARN)}ms，错误率 ≤ {ERROR_RATE_WARN * 100}%</p>"
    )

    for item in metrics["labels"]:
        if "tps" not in item and summary["tps"]:
            item["tps"] = round(summary["tps"] / max(len(metrics["labels"]), 1), 2)

    bottleneck = (
        "<ul>"
        f"<li><strong>现象</strong>：整体 P95 {summary['p95_ms']}ms，错误率 {summary['error_rate_pct']}%</li>"
        f"<li><strong>依据</strong>：{tool} 导出文件 {Path(metrics.get('source', '')).name}</li>"
        "<li><strong>推断</strong>：请结合应用日志、DB 慢查询与监控曲线进一步确认（本报告为自动汇总，不含资源层截图）</li>"
        "</ul>"
    )

    suggestions = (
        "<ol>"
        "<li>错误率 &gt; 0 时优先排查 5xx/超时与登录态失效</li>"
        "<li>P95 超 800ms 时检查 DB 索引、连接池与下游 RPC</li>"
        "<li>长压场景关注 GC、线程池队列与限流（429）</li>"
        "</ol>"
    )

    summary_sec = (
        f"<p>本次压测<strong>{pass_text}</strong>。"
        f"{'建议复测验证优化效果。' if not overall_ok else '可进入下一阶段评审。'}</p>"
    )

    screenshots = (
        '<div class="placeholder">无截图附件 — 可将 JMeter/k6 聚合报告截图保存到 output/ 后手动插入 HTML</div>'
    )

    replacements = {
        "{{REPORT_TITLE}}": title,
        "{{META_LINE}}": meta,
        "{{SECTION_OVERVIEW}}": overview,
        "{{SECTION_METRICS}}": _metrics_table_html(metrics["labels"]),
        "{{SECTION_SCREENSHOTS}}": screenshots,
        "{{SECTION_BOTTLENECK}}": bottleneck,
        "{{SECTION_SUGGESTIONS}}": suggestions,
        "{{SECTION_SUMMARY}}": summary_sec,
    }
    out = tpl
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="JMeter JTL / k6 JSON → HTML 性能报告")
    ap.add_argument("--jtl", type=Path, help="JMeter 结果 JTL（CSV）")
    ap.add_argument("--k6", type=Path, help="k6 --summary-export JSON")
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "output" / "perf_report.html")
    ap.add_argument("--title", default="性能测试分析报告")
    ap.add_argument("--scene", default="")
    ap.add_argument("--env", default="测试环境")
    ns = ap.parse_args()

    if bool(ns.jtl) == bool(ns.k6):
        ap.error("请指定 --jtl 或 --k6 之一")

    if ns.jtl:
        metrics = parse_jmeter_jtl(ns.jtl)
    else:
        metrics = parse_k6_summary(ns.k6)

    html = render_perf_report_html(metrics, title=ns.title, scene=ns.scene, environment=ns.env)
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(html, encoding="utf-8")
    print(f"已生成 HTML 报告: {ns.out.resolve()}")
    print(
        f"  请求={metrics['summary']['total_requests']} "
        f"P95={metrics['summary']['p95_ms']}ms "
        f"错误率={metrics['summary']['error_rate_pct']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
