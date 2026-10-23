#!/usr/bin/env python3
"""技能包 codegen 端到端自检（不启动真实服务 / 不跑 locust）。

运行（在 skills-专业版V3.0 根目录或任意目录）:
  python codegen/selftest_bundle.py
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "codegen" / "run_spec.py"
OUT = ROOT / "output" / "_selftest"
OUT.mkdir(parents=True, exist_ok=True)

EXCLUDE_LIST = ROOT / "codegen" / "excluded_doc_templates.txt"


def _load_excluded_template_names() -> set[str]:
    """用例/需求文档类 .md，无 YAML frontmatter，不走 generate.sh。"""
    if not EXCLUDE_LIST.is_file():
        return set()
    names: set[str] = set()
    for line in EXCLUDE_LIST.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            names.add(s)
    return names


def _find_git_bash() -> Path | None:
    for p in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
    ):
        if p.is_file():
            return p
    return None


def main() -> int:
    errs: list[tuple[str, str]] = []

    # 0) 关键路径存在
    must_exist = [
        ROOT / "generate.sh",
        ROOT / "codegen" / "run_spec.py",
        ROOT / "api-skills" / "索引.md",
        ROOT / "UI-skills" / "索引.md",
        ROOT / "intent-router" / "mapping.yaml",
        ROOT / "intent-router" / "SKILL.md",
        ROOT / "mobile-skills" / "执行" / "SKILL.md",
        ROOT / "progress-reporter" / "SKILL.md",
        ROOT / "data-factory" / "执行" / "SKILL.md",
        ROOT / "defect-sync" / "SKILL.md",
        ROOT / "scripts" / "AllureReport.ps1",
        ROOT / "codegen" / "fetch_perf_token.py",
        ROOT / "codegen" / "test_intent_router_mapping.py",
        ROOT / "intent-router" / "resolve_intent.py",
        ROOT / "mobile-skills" / "报告" / "SKILL.md",
        ROOT / "codegen" / "examples" / "hook_verify_fail.py",
        ROOT / "codegen" / "md_cases_to_appium_spec.py",
        ROOT / "codegen" / "testcase_to_appium_spec.py",
        ROOT / "rag-engine" / "scripts" / "rag_ingest.py",
        ROOT / "templates" / "appium_e2e.md",
        ROOT / "templates" / "perf_test_k6.md",
        ROOT / "templates" / "visual_regression.md",
    ]
    for p in must_exist:
        if not p.is_file():
            errs.append(("missing_file", str(p.relative_to(ROOT))))

    # 1) intent-router mapping 可解析
    try:
        import yaml  # noqa: PLC0415

        with open(ROOT / "intent-router" / "mapping.yaml", encoding="utf-8") as f:
            m = yaml.safe_load(f)
        assert isinstance(m, dict) and m.get("rules"), "mapping.rules 为空"
        tags = {r.get("tag") for r in m["rules"]}
        for t in ("api_automation", "ui_automation", "mobile_automation", "appium_pytest"):
            if t == "appium_pytest":
                found = any("appium_pytest" in (r.get("phrases") or []) for r in m["rules"])
                if not found:
                    errs.append(("mapping", "无 phrases 含 appium_pytest"))
            elif t not in tags:
                errs.append(("mapping", f"缺 tag: {t}"))
    except Exception as e:  # noqa: BLE001
        errs.append(("mapping_yaml", str(e)))

    # 2) --print-schema
    r = subprocess.run(
        [sys.executable, str(RUN), "--print-schema"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        errs.append(("print-schema", r.stderr))
    elif "appium_pytest" not in r.stdout:
        errs.append(("print-schema", "stdout 未包含 appium_pytest"))

    # 3) 全部 templates + codegen/examples（排除用例/需求文档，见 excluded_doc_templates.txt）
    users_csv = ROOT / "output" / "users.csv"
    users_csv.parent.mkdir(parents=True, exist_ok=True)
    if not users_csv.is_file():
        users_csv.write_text(
            "id,username,password\n1,admin,admin123\n2,user1,pass123\n",
            encoding="utf-8",
        )

    excluded = _load_excluded_template_names()
    specs = sorted(f for f in (ROOT / "templates").glob("*.md") if f.name not in excluded) + sorted(
        (ROOT / "codegen" / "examples").glob("*.md")
    )
    if not specs:
        errs.append(("specs", "未找到任何 spec .md"))
    for spec in specs:
        r = subprocess.run(
            [sys.executable, str(RUN), str(spec), "--validate-only"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            errs.append((f"validate {spec.relative_to(ROOT)}", r.stderr or r.stdout))
            continue
        meta: dict = {}
        try:
            import yaml  # noqa: PLC0415

            text = spec.read_text(encoding="utf-8")
            if text.startswith("---"):
                close = text.find("---", 3)
                if close > 0:
                    meta = yaml.safe_load(text[3:close]) or {}
                    kind = str(meta.get("kind") or "")
        except Exception:
            kind = ""
        if kind == "jmeter_test":
            ext = ".jmx"
        elif kind == "perf_test":
            engine = str(meta.get("engine") or "k6").strip().lower()
            ext = {"locust": ".py", "k6": ".js", "jmeter": ".jmx"}.get(engine, ".py")
        else:
            ext = ".py"
        outp = OUT / f"{spec.stem}_out{ext}"
        r = subprocess.run(
            [sys.executable, str(RUN), str(spec), "-o", str(outp)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            errs.append((f"generate {spec.relative_to(ROOT)}", r.stderr or r.stdout))
            continue
        if ext == ".jmx":
            if not outp.is_file() or "<jmeterTestPlan" not in outp.read_text(encoding="utf-8"):
                errs.append((f"generate {spec.relative_to(ROOT)}", "未生成有效 jmx"))
            continue
        if ext == ".js":
            if not outp.is_file() or "k6/http" not in outp.read_text(encoding="utf-8"):
                errs.append((f"generate {spec.relative_to(ROOT)}", "未生成有效 k6 js"))
            continue
        try:
            py_compile.compile(str(outp), doraise=True)
        except py_compile.PyCompileError as e:
            errs.append((f"compile {outp.name}", str(e)))
        if spec.stem == "ui_login" and outp.is_file():
            body = outp.read_text(encoding="utf-8")
            for needle in ("from ui_lib import", "run_ui_flow"):
                if needle not in body:
                    errs.append((f"ui_lib {outp.name}", f"缺少 {needle}"))
            if "_setup_test_data" not in body:
                errs.append((f"setup {outp.name}", "UI 缺 session setup fixture"))
        if spec.stem == "api_smoke" and outp.is_file():
            body = outp.read_text(encoding="utf-8")
            if "_setup_test_data" not in body:
                errs.append((f"setup {outp.name}", "API 缺 session setup fixture"))
            for needle in ("from api_lib import", "run_case", "var_pool"):
                if needle not in body:
                    errs.append((f"api_lib {outp.name}", f"缺少 {needle}"))
        if spec.stem == "api_health" and outp.is_file():
            body = outp.read_text(encoding="utf-8")
            if "_setup_test_data" in body:
                errs.append((f"setup {outp.name}", "api_health 应为 setup:none，不应含 _setup_test_data"))
        if spec.stem == "api_chain_vars" and outp.is_file():
            body = outp.read_text(encoding="utf-8")
            for needle in ("depends_on", "run_case", "${access_token}", "_check_case_depends"):
                if needle not in body:
                    errs.append((f"chain_vars {outp.name}", f"缺少 {needle}"))
        if spec.stem == "api_login_ddt" and outp.is_file():
            body = outp.read_text(encoding="utf-8")
            if "test_batch_execute" not in body or "run_batch" not in body:
                errs.append((f"ddt {outp.name}", "缺 batch + run_batch 数据驱动"))

    # 4) OpenAPI 导入（最小文档）
    mini = OUT / "mini_openapi.json"
    mini.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "Selftest", "version": "1"},
                "paths": {"/ping": {"get": {"responses": {"200": {"description": "ok"}}}}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_md = OUT / "imported_ping.md"
    r = subprocess.run(
        [
            sys.executable,
            str(RUN),
            "--import-openapi",
            str(mini),
            "-o",
            str(out_md),
            "--base-url",
            "http://your-server:9999",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        errs.append(("import-openapi", r.stderr or r.stdout))
    elif not out_md.is_file() or "kind:" not in out_md.read_text(encoding="utf-8"):
        errs.append(("import-openapi", "未生成有效 spec md"))

    # 4b) Appium 用例 → spec 规则映射
    ui_auto = ROOT / "output" / "_pipeline" / "seckill_ui_cases_ui_automation.json"
    if ui_auto.is_file():
        appium_spec = OUT / "appium_from_ui_cases.md"
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "codegen" / "testcase_to_appium_spec.py"),
                "-i",
                str(ui_auto),
                "-o",
                str(appium_spec),
                "--app-package",
                "com.selftest.demo",
                "--app-activity",
                ".Main",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            errs.append(("testcase_to_appium_spec", r.stderr or r.stdout))
        elif "kind: appium_pytest" not in appium_spec.read_text(encoding="utf-8"):
            errs.append(("testcase_to_appium_spec", "未生成 appium_pytest spec"))
    else:
        print("  跳过 testcase_to_appium_spec（无 seckill_ui_cases_ui_automation.json）", file=sys.stderr)

    # 4c) intent-router 话术回归
    r = subprocess.run(
        [sys.executable, str(ROOT / "codegen" / "test_intent_router_mapping.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        errs.append(("test_intent_router_mapping", r.stderr or r.stdout))

    # 5) pytest 仅收集（需已安装 pytest；不执行用例）
    pytest_targets = []
    for p in OUT.glob("*_out.py"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "import pytest" not in t:
            continue
        if "from locust" in t or "import locust" in t:
            continue
        pytest_targets.append(p)
    if not pytest_targets:
        errs.append(("pytest", "未找到含 import pytest 的生成物"))
    else:
        env = os.environ.copy()
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["PYTHONPATH"] = str(ROOT / "codegen") + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        passed, skipped, failed = 0, 0, 0
        skipped_names = []
        for p in sorted(pytest_targets):
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q", str(p)],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                env=env,
            )
            if r.returncode == 0:
                passed += 1
            elif "No module named" in (r.stderr + r.stdout) or "ModuleNotFoundError" in (r.stderr + r.stdout):
                skipped += 1
                skipped_names.append(p.name)
                continue
            else:
                failed += 1
                errs.append((f"pytest_collect {p.name}", (r.stdout + "\n" + r.stderr)[-2000:]))
        if skipped:
            print(f"  跳过 {skipped} 个因缺失依赖无法收集的文件: {', '.join(skipped_names)}", file=sys.stderr)
        if passed == 0 and failed > 0:
            errs.append(("pytest", "全部 pytest 文件收集失败"))
        else:
            print(
                f"  pytest collect: {passed} 通过, {skipped} 跳过(缺依赖), {failed} 失败",
                file=sys.stderr,
            )
        for p in pytest_targets:
            tree = ast.parse(p.read_text(encoding="utf-8"))
            has_test = any(
                isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
                for n in tree.body
            )
            if not has_test:
                errs.append((f"ast_tests {p.name}", "无顶层 test_* 函数"))

    # 6) generate.sh（Linux bash 或 Git Bash）
    gen_cmd = ["/bin/bash", str(ROOT / "generate.sh"), "templates/api_smoke.md"]
    if sys.platform == "win32":
        bash = _find_git_bash()
        if bash is not None:
            gen_cmd = [str(bash), "-lc", f'cd "{ROOT.as_posix()}" && ./generate.sh templates/api_smoke.md']
        else:
            bash = None
    else:
        bash = "/bin/bash"
    if bash is not None:
        r = subprocess.run(
            gen_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            errs.append(("generate.sh api_smoke", (r.stderr or r.stdout)[-2000:]))
    else:
        print("# 跳过 generate.sh（Windows 未检测到 Git Bash）", file=sys.stderr)

    if errs:
        print(f"自测失败: {len(errs)} 项", file=sys.stderr)
        for name, msg in errs:
            print("---", name, "---", file=sys.stderr)
            print(msg[:6000], file=sys.stderr)
        return 1

    print(
        "自测通过:",
        len(specs),
        "个 spec 校验+生成+编译;",
        len(pytest_targets),
        "个 pytest 产物 collect-only OK",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
