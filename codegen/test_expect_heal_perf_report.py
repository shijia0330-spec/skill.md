"""P2-9 expect 自愈 + P2-11 压测报告 codegen。"""
from __future__ import annotations

import sys
from pathlib import Path

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from perf_report_from_results import parse_jmeter_jtl, render_perf_report_html
from ui_lib.expect_healer import _heal_alternatives, is_healable_expect


def test_heal_alternatives_visible_text():
    ex = {"type": "visible_text", "text": "商品总数统计", "exact": True}
    alts = _heal_alternatives(ex)
    assert any(a.get("exact") is False for a in alts)


def test_is_healable_expect():
    assert is_healable_expect({"type": "url_regex", "pattern": "/dashboard"})
    assert not is_healable_expect({"type": "table_row_count", "count": 3})


def test_parse_jmeter_jtl_real_sample():
    jtl = _CODEGEN.parent / "output" / "perf_test.jtl"
    if not jtl.is_file():
        return
    metrics = parse_jmeter_jtl(jtl)
    assert metrics["summary"]["total_requests"] > 0
    assert metrics["summary"]["p95_ms"] >= 0
    assert len(metrics["labels"]) >= 1


def test_render_perf_report_html(tmp_path: Path):
    metrics = {
        "tool": "JMeter",
        "source": "test.jtl",
        "labels": [
            {
                "label": "GET /api/x",
                "samples": 100,
                "avg_ms": 50.0,
                "p95_ms": 120.0,
                "error_rate": 0.0,
                "verdict": "✅",
                "verdict_class": "ok",
                "tps": 10.0,
            }
        ],
        "summary": {
            "total_requests": 100,
            "total_errors": 0,
            "error_rate_pct": 0.0,
            "p95_ms": 120.0,
            "tps": 10.0,
            "duration_sec": 10.0,
        },
    }
    html = render_perf_report_html(metrics, title="测试报告")
    assert "测试报告" in html
    assert "GET /api/x" in html
    out = tmp_path / "r.html"
    out.write_text(html, encoding="utf-8")
    assert out.stat().st_size > 500
