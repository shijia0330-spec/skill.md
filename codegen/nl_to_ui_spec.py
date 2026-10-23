#!/usr/bin/env python3
"""
自然语言 → ui_pytest_playwright spec Markdown（NL → spec → generate 闭环第一步）。

用法:
  python codegen/nl_to_ui_spec.py "打开登录页，用户名：admin，密码：admin123，点击登录" \\
      -o templates/nl_login_demo.md --base-url http://your-server:5001

  # 解析 + 写 spec + 生成 pytest
  python codegen/nl_to_ui_spec.py "..." -o templates/nl_login_demo.md --generate

  # 从文件读 NL
  python codegen/nl_to_ui_spec.py -i intent.txt -o templates/from_nl.md

下一步:
  ./generate.sh templates/nl_login_demo.md
  python -m pytest output/nl_login_demo.py -v
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from ui_lib.nl_parser import parse_nl_to_flow


def slug_from_text(text: str, *, max_len: int = 48) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", s).strip("_")
    if not s:
        s = "flow"
    if s[0].isdigit():
        s = "nl_" + s
    return s[:max_len]


def build_spec_meta(
    steps: list[dict[str, Any]],
    expects: list[dict[str, Any]],
    *,
    base_url: str,
    viewport: dict[str, int] | None = None,
    healing: bool = True,
    pretest: bool = False,
    flow_name: str | None = None,
    nl_source: str | None = None,
) -> dict[str, Any]:
    vp = viewport or {"width": 1280, "height": 720}
    meta: dict[str, Any] = {
        "kind": "ui_pytest_playwright",
        "base_url": base_url.rstrip("/"),
        "viewport": vp,
        "healing": healing,
    }
    if pretest:
        meta["pretest"] = True

    if flow_name:
        meta["flows"] = [{"name": flow_name, "steps": steps, "expect": expects or []}]
    else:
        meta["steps"] = steps
        if expects:
            meta["expect"] = expects

    if nl_source:
        meta["nl_source"] = nl_source[:500]
        meta["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    return meta


def build_markdown(
    meta: dict[str, Any],
    *,
    title: str | None = None,
    nl_text: str | None = None,
) -> str:
    if yaml is None:
        raise RuntimeError("需要 PyYAML: pip install PyYAML")

    payload = dict(meta)
    nl_src = payload.pop("nl_source", None)
    payload.pop("generated_at", None)

    fm = yaml.safe_dump(payload, allow_unicode=True, default_flow_style=False, sort_keys=False).rstrip()

    if not title:
        title = "NL 生成的 UI spec"

    body_lines = [
        f"# {title}",
        "",
        "由 `codegen/nl_to_ui_spec.py` 从自然语言自动生成。",
        "",
        "## 下一步",
        "",
        "```bash",
        "./generate.sh templates/<本文件>.md",
        "python -m pytest output/<同名>.py -v",
        "```",
    ]
    if nl_text or nl_src:
        body_lines.extend(["", "## 原始 NL", "", "```", (nl_text or nl_src or "").strip(), "```"])

    return f"---\n{fm}\n---\n" + "\n".join(body_lines) + "\n"


def nl_text_to_spec(
    text: str,
    *,
    base_url: str = "http://your-server:5001",
    parser: str | None = None,
    flow_name: str | None = None,
    viewport: dict[str, int] | None = None,
    healing: bool = True,
    pretest: bool = False,
    title: str | None = None,
) -> tuple[str, dict[str, Any]]:
    steps, expects = parse_nl_to_flow(text, base_url, parser=parser)
    if not steps:
        raise ValueError("未能从自然语言解析出任何步骤，请换表述或设置 NL_PARSER=llm")

    name = flow_name or slug_from_text(text)
    meta = build_spec_meta(
        steps,
        expects,
        base_url=base_url,
        viewport=viewport,
        healing=healing,
        pretest=pretest,
        flow_name=name,
        nl_source=text,
    )
    md = build_markdown(meta, title=title or f"NL UI — {name}", nl_text=text)
    return md, meta


def run_generate(spec_path: Path, *, out_dir: Path | None = None) -> Path:
    root = _CODEGEN.parent
    run_spec = _CODEGEN / "run_spec.py"
    out = out_dir or (root / "output" / (spec_path.stem + ".py"))
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(run_spec), str(spec_path), "-o", str(out)],
        check=True,
        cwd=str(root),
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", help="自然语言描述（与 -i 二选一）")
    ap.add_argument("-i", "--input", type=Path, help="从文件读取 NL 文本")
    ap.add_argument("-o", "--output", type=Path, help="输出 .md 路径；省略则打印到 stdout")
    ap.add_argument("--base-url", default="http://your-server:5001")
    ap.add_argument("--parser", choices=["auto", "llm", "regex"], default=None)
    ap.add_argument("--flow-name", default=None, help="flows[].name，默认从 NL  slug")
    ap.add_argument("--title", default=None)
    ap.add_argument("--no-healing", action="store_true")
    ap.add_argument("--pretest", action="store_true")
    ap.add_argument("--generate", action="store_true", help="写 spec 后立即 run_spec 生成 pytest")
    ap.add_argument("--out-py", type=Path, help="--generate 时 pytest 输出路径")
    ns = ap.parse_args()

    root = _CODEGEN.parent

    def _abs(p: Path) -> Path:
        return p if p.is_absolute() else (root / p).resolve()

    if ns.input:
        text = _abs(ns.input).read_text(encoding="utf-8").strip()
    elif ns.text:
        text = ns.text.strip()
    else:
        ap.error("请提供 NL 文本参数或 -i 文件")

    md, meta = nl_text_to_spec(
        text,
        base_url=ns.base_url.rstrip("/"),
        parser=ns.parser,
        flow_name=ns.flow_name,
        healing=not ns.no_healing,
        pretest=ns.pretest,
        title=ns.title,
    )

    if ns.output:
        out = _abs(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"已写入 spec: {out}", file=sys.stderr)
        if ns.generate:
            py = run_generate(out, out_dir=_abs(ns.out_py) if ns.out_py else None)
            print(f"已生成 pytest: {py}", file=sys.stderr)
    else:
        sys.stdout.write(md)

    if not meta.get("steps") and not meta.get("flows"):
        sys.exit(1)


if __name__ == "__main__":
    main()
