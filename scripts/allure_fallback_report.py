#!/usr/bin/env python3
"""从 allure-results 生成可离线打开的独立 HTML 报告（双击即可，无 500）。"""
from __future__ import annotations

import base64
import html
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "output" / "allure-results"
DEFAULT_OUT = ROOT / "output" / "allure-report" / "standalone.html"
SESSION_WINDOW_SEC = int(os.environ.get("ALLURE_REPORT_SESSION_SEC", "600"))

TEST_TYPE_LABELS = {
    "api": "API 接口",
    "ui": "UI 界面",
}

LAYER_ORDER = ("H", "X", "E", "其他")

_PANEL_COUNTER = 0


def _next_panel_id() -> str:
    global _PANEL_COUNTER
    _PANEL_COUNTER += 1
    return f"panel-{_PANEL_COUNTER}"


def _latest_session_files(results_dir: Path) -> list[Path]:
    files = sorted(results_dir.glob("*-result.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return []
    include_filter = os.environ.get("ALLURE_REPORT_INCLUDE", "").strip()
    if include_filter:
        patterns = [p.strip() for p in include_filter.split(",") if p.strip()]
        files = [f for f in files if any(_load_result_name(f).find(p) >= 0 for p in patterns)]
        if not files:
            return []
    latest_mtime = files[0].stat().st_mtime
    return [f for f in files if latest_mtime - f.stat().st_mtime <= SESSION_WINDOW_SEC]


def _load_result_name(p: Path) -> str:
    data = _load_json(p)
    if isinstance(data, dict):
        return str(data.get("name") or "")
    return ""


def _failure_summary(data: dict) -> str:
    sd = data.get("statusDetails") or {}
    msg = str(sd.get("message") or "").strip()
    if msg:
        return msg.splitlines()[0][:500]
    return str(data.get("description") or "").strip()


def _load_json(p: Path) -> dict | list | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _labels_map(data: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for lb in data.get("labels") or []:
        if isinstance(lb, dict):
            name = str(lb.get("name") or "")
            value = str(lb.get("value") or "")
            if name:
                out[name] = value
    return out


def _report_title() -> tuple[str, str, str]:
    test_type = os.environ.get("ALLURE_TEST_TYPE", "").strip().lower()
    business = os.environ.get("ALLURE_BUSINESS", "").strip()
    type_label = TEST_TYPE_LABELS.get(test_type, test_type.upper() or "测试")
    title = f"{type_label}测试报告"
    if business:
        title = f"{title} · {business}"
    return title, type_label, business


def _collect_steps(steps: list, out: list, indent: int = 0) -> None:
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        out.append((indent, str(s.get("name") or ""), str(s.get("status") or ""), list(s.get("attachments") or [])))
        _collect_steps(s.get("steps") or [], out, indent + 1)


def _http_method_badge(step_name: str) -> str:
    name = step_name.strip().upper()
    for m in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        if name.startswith(m + " "):
            return f'<span class="http-method {m.lower()}">{m}</span>'
    return ""


def _render_code_panel(title: str, text: str, *, default_open: bool = False, kind: str = "") -> str:
    pid = _next_panel_id()
    open_attr = " open" if default_open else ""
    kind_cls = f" panel-{kind}" if kind else ""
    safe_title = html.escape(title)
    return (
        f'<details class="code-panel{kind_cls}" id="{pid}"{open_attr}>'
        f'<summary class="code-panel-head">'
        f'<span class="code-panel-title">{safe_title}</span>'
        f'<span class="code-panel-actions">'
        f'<button type="button" class="btn-copy" data-target="{pid}" '
        f'onclick="copyPanel(this); event.stopPropagation();">复制</button>'
        f"</span></summary>"
        f'<div class="code-panel-body"><pre><code>{html.escape(text)}</code></pre></div>'
        f"</details>"
    )


def _render_attachment(att_dir: Path, att: dict, *, step_status: str = "") -> str:
    if not isinstance(att, dict):
        return ""
    src = att.get("source")
    raw_name = str(att.get("name") or src or "attachment")
    name = html.escape(raw_name)
    if not src:
        return ""
    path = att_dir / str(src)
    if not path.is_file():
        return f'<div class="att missing">{name}（文件缺失）</div>'

    mime = str(att.get("type") or "")
    raw = path.read_bytes()
    if mime.startswith("image/"):
        b64 = base64.b64encode(raw).decode("ascii")
        return (
            f'<details class="code-panel panel-image">'
            f'<summary class="code-panel-head"><span class="code-panel-title">{name}</span></summary>'
            f'<div class="code-panel-body img-wrap">'
            f'<img src="data:{mime};base64,{b64}" alt="{name}"/>'
            f"</div></details>"
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if mime.endswith("json") or path.suffix == ".json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 请求/响应：可折叠 + 复制；失败用例默认展开响应
    if raw_name == "请求":
        return _render_code_panel("请求 Request", text, default_open=True, kind="request")
    if raw_name == "响应":
        open_resp = step_status in ("failed", "broken")
        return _render_code_panel("响应 Response", text, default_open=open_resp, kind="response")
    return _render_code_panel(raw_name, text, default_open=False)


def _steps_html(results_dir: Path, rows: list[tuple[int, str, str, list]], *, summary: str = "") -> str:
    if rows:
        lines = ['<div class="steps">']
        for indent, name, status, atts in rows:
            cls = status if status in ("passed", "failed", "broken", "skipped") else ""
            method_badge = _http_method_badge(name)
            att_html = "".join(_render_attachment(results_dir, a, step_status=status) for a in atts)
            lines.append(
                f'<div class="step-item {cls}" style="margin-left:{indent * 16}px">'
                f'<div class="step-head">'
                f"{method_badge}"
                f'<span class="step-name">{html.escape(name)}</span>'
                f'<span class="badge {cls}">{html.escape(status)}</span>'
                f"</div>"
                f'<div class="step-atts">{att_html}</div>'
                f"</div>"
            )
        lines.append("</div>")
        return "\n".join(lines)
    if summary:
        return (
            '<p class="no-steps">未记录逐步操作。</p>'
            + _render_code_panel("摘要", summary, default_open=False)
        )
    return '<p class="no-steps">未记录逐步操作。</p>'


def _render_test_block(results_dir: Path, test: dict) -> str:
    st = test["status"]
    labels = test.get("labels") or {}
    meta_bits = []
    if labels.get("layer"):
        meta_bits.append(f"分层 {labels['layer']}")
    if labels.get("priority"):
        meta_bits.append(f"优先级 {labels['priority']}")
    if labels.get("story"):
        meta_bits.append(html.escape(labels["story"]))
    meta = " · ".join(meta_bits)
    failed = st in ("failed", "broken")
    open_attr = " open" if failed else ""

    inner = []
    if meta:
        inner.append(f"<p class='case-meta'>{meta}</p>")
    if test.get("description"):
        inner.append(f"<p class='case-desc'>{html.escape(test['description'])}</p>")
    inner.append(_steps_html(results_dir, test["steps"], summary=test.get("summary") or ""))

    return (
        f'<details class="test-case {st}"{open_attr}>'
        f'<summary class="test-case-head">'
        f'<span class="test-case-name">{html.escape(test["name"])}</span>'
        f'<span class="badge {st}">{html.escape(st)}</span>'
        f"</summary>"
        f'<div class="test-case-body">{"".join(inner)}</div>'
        f"</details>"
    )


def _layer_sort_key(layer: str) -> tuple[int, str]:
    layer_u = layer.upper()
    if layer_u in LAYER_ORDER:
        return (LAYER_ORDER.index(layer_u), layer_u)
    return (len(LAYER_ORDER), layer)


def _report_styles() -> str:
    return """
:root {
  --bg: #0f1419;
  --surface: #1a2332;
  --surface2: #243044;
  --border: #2d3a4f;
  --text: #e7ecf3;
  --muted: #8b9cb3;
  --accent: #3b82f6;
  --pass: #22c55e;
  --fail: #ef4444;
  --req: #6366f1;
  --res: #0ea5e9;
  --radius: 10px;
  --mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}
* { box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  margin: 0;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.wrap { max-width: 1200px; margin: 0 auto; padding: 24px 20px 48px; }
h1 { margin: 0 0 6px; font-size: 1.75rem; font-weight: 600; }
.meta { color: var(--muted); margin-bottom: 16px; font-size: 0.9rem; }
.toolbar {
  display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px;
}
.toolbar button {
  background: var(--surface2); color: var(--text); border: 1px solid var(--border);
  padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
}
.toolbar button:hover { background: var(--border); }
.summary { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 20px; flex: 1; min-width: 120px;
}
.card span { color: var(--muted); font-size: 0.85rem; }
.card b { font-size: 2rem; display: block; margin-top: 4px; font-weight: 600; }
.card b.pass { color: var(--pass); }
.card b.fail { color: var(--fail); }
.dim-tags { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.tag {
  background: rgba(59,130,246,.15); color: #93c5fd;
  padding: 4px 12px; border-radius: 999px; font-size: 0.82rem;
  border: 1px solid rgba(59,130,246,.3);
}
.note {
  background: rgba(234,179,8,.08); border: 1px solid rgba(234,179,8,.25);
  padding: 12px 14px; border-radius: var(--radius); margin-bottom: 20px;
  font-size: 0.85rem; color: #fcd34d;
}
.note code { background: rgba(0,0,0,.25); padding: 2px 6px; border-radius: 4px; }
h2.section-title {
  font-size: 1.1rem; margin: 28px 0 12px; padding: 0;
  color: var(--muted); font-weight: 500; letter-spacing: .02em;
}
.layer-block {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 12px 14px; margin: 12px 0;
}
.layer-block > h3 {
  margin: 0 0 12px; font-size: 0.95rem; color: var(--muted);
  font-weight: 500; padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.test-case {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; margin: 8px 0; overflow: hidden;
}
.test-case.failed, .test-case.broken { border-color: rgba(239,68,68,.45); }
.test-case-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; cursor: pointer; list-style: none; gap: 12px;
  user-select: none;
}
.test-case-head::-webkit-details-marker { display: none; }
.test-case-head::before {
  content: '▸'; color: var(--muted); margin-right: 4px; transition: transform .15s;
}
.test-case[open] > .test-case-head::before { transform: rotate(90deg); }
.test-case-name { font-family: var(--mono); font-size: 0.88rem; flex: 1; word-break: break-all; }
.test-case-body { padding: 0 14px 14px; border-top: 1px solid var(--border); }
.case-meta, .case-desc { font-size: 0.85rem; color: var(--muted); margin: 10px 0 6px; }
.steps { margin-top: 8px; }
.step-item {
  background: rgba(0,0,0,.2); border-radius: 8px; padding: 10px 12px; margin: 8px 0;
  border-left: 3px solid var(--border);
}
.step-item.passed { border-left-color: var(--pass); }
.step-item.failed, .step-item.broken { border-left-color: var(--fail); }
.step-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.step-name { font-family: var(--mono); font-size: 0.85rem; }
.http-method {
  font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;
  font-family: var(--mono);
}
.http-method.get { background: rgba(34,197,94,.2); color: #86efac; }
.http-method.post { background: rgba(59,130,246,.2); color: #93c5fd; }
.http-method.put { background: rgba(234,179,8,.2); color: #fde047; }
.http-method.patch { background: rgba(168,85,247,.2); color: #d8b4fe; }
.http-method.delete { background: rgba(239,68,68,.2); color: #fca5a5; }
.badge {
  font-size: 0.72rem; padding: 2px 10px; border-radius: 999px;
  text-transform: lowercase; font-weight: 500;
}
.badge.passed { background: rgba(34,197,94,.2); color: #86efac; }
.badge.failed, .badge.broken { background: rgba(239,68,68,.2); color: #fca5a5; }
.badge.skipped { background: rgba(148,163,184,.2); color: #cbd5e1; }
.code-panel {
  margin: 6px 0; border: 1px solid var(--border); border-radius: 8px;
  background: #0d1117; overflow: hidden;
}
.code-panel.panel-request { border-color: rgba(99,102,241,.35); }
.code-panel.panel-response { border-color: rgba(14,165,233,.35); }
.code-panel-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; cursor: pointer; background: rgba(255,255,255,.03);
  list-style: none; user-select: none;
}
.code-panel-head::-webkit-details-marker { display: none; }
.code-panel-head::before {
  content: '▸'; color: var(--muted); margin-right: 8px; font-size: 0.75rem;
  transition: transform .15s;
}
.code-panel[open] > .code-panel-head::before { transform: rotate(90deg); }
.code-panel-title { font-size: 0.85rem; font-weight: 500; }
.panel-request .code-panel-title { color: #a5b4fc; }
.panel-response .code-panel-title { color: #7dd3fc; }
.code-panel-actions { display: flex; gap: 6px; }
.btn-copy {
  background: transparent; border: 1px solid var(--border); color: var(--muted);
  padding: 3px 10px; border-radius: 5px; cursor: pointer; font-size: 0.78rem;
}
.btn-copy:hover { color: var(--text); border-color: var(--accent); }
.btn-copy.copied { color: var(--pass); border-color: var(--pass); }
.code-panel-body { border-top: 1px solid var(--border); max-height: 420px; overflow: auto; }
.code-panel-body pre {
  margin: 0; padding: 12px 14px; font-family: var(--mono); font-size: 0.8rem;
  line-height: 1.45; white-space: pre-wrap; word-break: break-word;
  color: #c9d1d9;
}
.code-panel-body img { max-width: 100%; display: block; padding: 12px; }
.no-steps { color: var(--muted); font-size: 0.85rem; margin: 8px 0; }
.att.missing { color: var(--fail); font-size: 0.85rem; padding: 8px; }
"""


def _report_scripts() -> str:
    return """
<script>
function copyPanel(btn) {
  var panel = document.getElementById(btn.getAttribute('data-target'));
  if (!panel) return;
  var code = panel.querySelector('code');
  var text = code ? code.textContent : '';
  function ok() {
    btn.textContent = '已复制';
    btn.classList.add('copied');
    setTimeout(function() {
      btn.textContent = '复制';
      btn.classList.remove('copied');
    }, 1600);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(ok).catch(fallback);
  } else {
    fallback();
  }
  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); ok(); } catch(e) {}
    document.body.removeChild(ta);
  }
}
function toggleAll(selector, open) {
  document.querySelectorAll(selector).forEach(function(el) {
    if (open) el.setAttribute('open', '');
    else el.removeAttribute('open');
  });
}
document.getElementById('btn-expand-cases')?.addEventListener('click', function() {
  toggleAll('.test-case', true);
});
document.getElementById('btn-collapse-cases')?.addEventListener('click', function() {
  toggleAll('.test-case', false);
});
document.getElementById('btn-expand-panels')?.addEventListener('click', function() {
  toggleAll('.code-panel', true);
});
document.getElementById('btn-collapse-panels')?.addEventListener('click', function() {
  toggleAll('.code-panel', false);
});
</script>
"""


def build_html(results_dir: Path) -> str:
    global _PANEL_COUNTER
    _PANEL_COUNTER = 0

    tests: list[dict] = []
    setup_steps: list[tuple[int, str, str, list]] = []
    result_files = _latest_session_files(results_dir)
    session_note = ""
    if not result_files:
        result_files = sorted(results_dir.glob("*-result.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
        session_note = "（未匹配到最近会话，仅展示最新 1 条）"

    default_business = os.environ.get("ALLURE_BUSINESS", "").strip() or "未分类业务"

    for p in result_files:
        data = _load_json(p)
        if not isinstance(data, dict):
            continue
        labels = _labels_map(data)
        steps_flat: list[tuple[int, str, str, list]] = []
        _collect_steps(data.get("steps") or [], steps_flat)
        tests.append(
            {
                "name": data.get("name") or p.stem,
                "description": data.get("description") or "",
                "status": data.get("status") or "",
                "steps": steps_flat,
                "summary": _failure_summary(data),
                "labels": labels,
                "business": labels.get("business") or labels.get("epic") or default_business,
                "layer": labels.get("layer") or "其他",
                "feature": labels.get("feature") or "",
            }
        )

    seen_names: set[str] = set()
    deduped: list[dict] = []
    for t in tests:
        key = t["name"]
        if key in seen_names:
            continue
        seen_names.add(key)
        deduped.append(t)

    if result_files:
        latest_mtime = max(f.stat().st_mtime for f in result_files)
        for p in sorted(results_dir.glob("*-container.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            if latest_mtime - p.stat().st_mtime > SESSION_WINDOW_SEC:
                continue
            data = _load_json(p)
            if not isinstance(data, dict):
                continue
            for before in data.get("befores") or []:
                if isinstance(before, dict) and before.get("name") == "_setup_test_data":
                    _collect_steps(before.get("steps") or [], setup_steps)
                    break
            if setup_steps:
                break

    passed = sum(1 for t in deduped if t["status"] == "passed")
    total = len(deduped)
    failed_count = total - passed
    title, type_label, business = _report_title()

    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for t in deduped:
        grouped[t["business"]][t["layer"]].append(t)

    body: list[str] = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{html.escape(title)}</title>",
        f"<style>{_report_styles()}</style>",
        "</head><body><div class='wrap'>",
        f"<h1>{html.escape(title)}</h1>",
        "<p class='meta'>独立 HTML · 最近一次 pytest 会话 · 请求/响应可折叠 · 支持一键复制</p>",
        "<div class='dim-tags'>",
        f"<span class='tag'>测试类型：{html.escape(type_label)}</span>",
        f"<span class='tag'>业务域：{html.escape(business or '未指定')}</span>",
        "</div>",
        "<div class='toolbar'>",
        "<button type='button' id='btn-expand-cases'>展开全部用例</button>",
        "<button type='button' id='btn-collapse-cases'>折叠全部用例</button>",
        "<button type='button' id='btn-expand-panels'>展开全部请求/响应</button>",
        "<button type='button' id='btn-collapse-panels'>折叠全部请求/响应</button>",
        "</div>",
    ]
    if session_note:
        body.append(f"<div class='note'>{html.escape(session_note)}</div>")

    body += [
        f"<div class='summary'>"
        f"<div class='card'><span>用例</span><b>{total}</b></div>"
        f"<div class='card'><span>通过</span><b class='pass'>{passed}</b></div>"
        f"<div class='card'><span>失败</span><b class='fail'>{failed_count}</b></div>"
        f"</div>",
    ]

    if setup_steps:
        body.append("<h2 class='section-title'>Step 1 · 测试数据铺底</h2>")
        body.append(_steps_html(results_dir, setup_steps))

    for biz_name in sorted(grouped.keys()):
        body.append(f"<h2 class='section-title'>业务域 · {html.escape(biz_name)}</h2>")
        layers = grouped[biz_name]
        for layer in sorted(layers.keys(), key=_layer_sort_key):
            layer_tests = layers[layer]
            feature = layer_tests[0].get("feature") if layer_tests else ""
            layer_title = feature or f"{layer} · 分层"
            body.append(f"<div class='layer-block'><h3>{html.escape(layer_title)}</h3>")
            for t in layer_tests:
                body.append(_render_test_block(results_dir, t))
            body.append("</div>")

    body += ["</div>", _report_scripts(), "</body></html>"]
    return "\n".join(body)


def main() -> int:
    in_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    if not in_dir.is_dir():
        print(f"目录不存在: {in_dir}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(in_dir), encoding="utf-8")
    print(f"已写入: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
