#!/usr/bin/env python3
"""
功能用例 Markdown → api_pytest spec（一键流水线）。

Step 1  解析 *_testcases.md（#### 编号 + 评审表优先级）
Step 2  规则映射为 cases[]（含 automation 块）
Step 3  testcase_to_api_spec.py → templates/*.md

用法:
  python codegen/md_cases_to_api_spec.py \\
      -i output/seckill_auth_testcases.md \\
      -o templates/seckill_api_from_cases.md \\
      --base-url http://127.0.0.1:5001 \\
      --priority P0,P1

  ./generate.sh templates/seckill_api_from_cases.md --report
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CODEGEN = Path(__file__).resolve().parent

CASE_HEADING = re.compile(r"^####\s+(?P<id>\S+)\s+(?P<title>.+?)\s*$")
REVIEW_ROW = re.compile(r"^\|\s*(?P<id>[A-Z]+-\d+)\s*\|")
HTTP_PATH = re.compile(
    r"\b(?P<method>GET|POST|PUT|PATCH|DELETE)\s+(/api/[a-zA-Z0-9_./{}-]+)",
    re.I,
)
HTTP_CODE = re.compile(r"\bHTTP\s+(?P<code>\d{3})\b", re.I)
HTTP_4XX = re.compile(r"\bHTTP\s+4xx\b", re.I)


def _resolve(p: Path) -> Path:
    return p if p.is_absolute() else (ROOT / p).resolve()


def parse_review_table(text: str) -> dict[str, dict[str, str]]:
    """用例评审表：编号 → {priority, case_type, tags}"""
    out: dict[str, dict[str, str]] = {}
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("| 编号 |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            in_table = False
            continue
        if re.match(r"^\|\s*-+\s*\|", line):
            continue
        parts = [c.strip() for c in line.strip("|").split("|")]
        if len(parts) < 4:
            continue
        cid = parts[0]
        if not re.match(r"^[A-Z]+-\d+$", cid):
            continue
        out[cid] = {
            "priority": parts[2] if len(parts) > 2 else "P2",
            "case_type": parts[3] if len(parts) > 3 else "",
            "tags": parts[4] if len(parts) > 4 else "",
        }
    return out


def parse_api_cases(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    cases: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        m = CASE_HEADING.match(lines[i])
        if not m:
            i += 1
            continue
        case_id = m.group("id")
        title = m.group("title").strip()
        steps: list[str] = []
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if nxt.startswith("#### ") or nxt.startswith("### ") or nxt.startswith("## "):
                break
            if nxt.startswith("- "):
                steps.append(nxt[2:].strip())
            i += 1
        cases.append({"case_id": case_id, "title": title, "steps": steps})
    return cases


def _a_chars(n: int) -> str:
    return "a" * max(0, n)


def _expect_from_steps(steps: list[str], default: int = 200) -> int | list[int]:
    blob = " ".join(steps)
    if HTTP_4XX.search(blob):
        return [400, 422]
    m = HTTP_CODE.search(blob)
    if m:
        return int(m.group("code"))
    if "401" in blob:
        return 401
    if "400" in blob or "409" in blob:
        if "409" in blob:
            return 409
        return 400
    if "201" in blob:
        return 201
    if "200" in blob:
        return 200
    return default


def _layer_for(case_id: str, expect: Any) -> str:
    if case_id.startswith("F-"):
        return "H"
    if case_id.startswith("E-"):
        return "E"
    if case_id.startswith("V-") or case_id.startswith("X-"):
        return "X"
    if isinstance(expect, list) or (isinstance(expect, int) and expect >= 400):
        return "X"
    return "H"


def _automation_id(case_id: str) -> str:
    return "TC-AUTH-" + case_id.replace("-", "")


def build_automation(case_id: str, title: str, steps: list[str]) -> dict[str, Any] | None:
    """规则映射：秒杀财务认证模块 API 用例。"""
    blob = " ".join(steps)
    expect = _expect_from_steps(steps)

    # 不可自动化 / 需人工
    if case_id == "E-01":
        return {
            "id": _automation_id(case_id),
            "method": "GET",
            "path": "/api/auth/profile",
            "expect_status": 200,
            "review_required": True,
            "skip_reason": "JWT 24h 过期需改时钟或 mock，见 T-03",
        }
    if case_id == "P-02":
        return None  # 依赖 C-01 注册链，暂不单步

    uname = f"skills_{case_id.lower()}_{{{{timestamp}}}}"
    pwd = "abc123"
    email = f"skills_{case_id.lower()}_{{{{timestamp}}}}@example.com"

    # ── 注册 ──
    if case_id == "C-01":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": pwd, "email": email},
            "expect_status": 201,
        }
    if case_id == "C-02":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": pwd},
            "expect_status": [201, 400],
            "review_required": True,
        }
    if case_id in ("V-01", "V-10"):
        body: dict[str, Any] = {"password": pwd, "email": email}
        if case_id == "V-10":
            body = {"username": uname, "email": email}
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": body,
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id in ("V-02", "V-03"):
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {
                "username": "" if case_id == "V-02" else "   ",
                "password": pwd,
            },
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id == "V-04":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"password": pwd},
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id == "V-05":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": "a", "password": pwd},
            "expect_status": 201,
        }
    if case_id == "V-06":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": _a_chars(50), "password": pwd},
            "expect_status": 201,
        }
    if case_id == "V-07":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": _a_chars(51), "password": pwd},
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id == "V-08":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": "user@name", "password": pwd},
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id == "V-09":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": f"buyer_01-test_{{{{timestamp}}}}", "password": pwd},
            "expect_status": 201,
        }
    if case_id == "V-11":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": "12345"},
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id == "V-12":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": "123456"},
            "expect_status": 201,
        }
    if case_id == "V-13":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": "1234567"},
            "expect_status": 201,
        }
    if case_id == "V-14":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {
                "username": "__ENV__:TEST_USERNAME",
                "password": pwd,
                "email": "dup@example.com",
            },
            "expect_status": [400, 409],
        }
    if case_id == "V-15":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": pwd, "email": "not-an-email"},
            "expect_status": [400, 422],
            "review_required": True,
        }
    if case_id == "V-16":
        long_email = _a_chars(90) + "@example.com"  # >100 chars
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/register",
            "no_auth": True,
            "json_body": {"username": uname, "password": pwd, "email": long_email},
            "expect_status": [400, 422],
            "review_required": True,
        }

    # ── 登录 ──
    if case_id == "L-01":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/login",
            "no_auth": True,
            "json_body": {
                "username": "__ENV__:TEST_USERNAME",
                "password": "__ENV__:TEST_PASSWORD",
            },
            "expect_status": 200,
        }
    if case_id == "V-17":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/login",
            "no_auth": True,
            "json_body": {
                "username": "__ENV__:TEST_USERNAME",
                "password": "wrong_pass",
            },
            "expect_status": 401,
        }
    if case_id == "V-18":
        return {
            "id": _automation_id(case_id),
            "method": "POST",
            "path": "/api/auth/login",
            "no_auth": True,
            "json_body": {"username": "no_such_user_xyz", "password": pwd},
            "expect_status": [401, 404],
            "review_required": True,
        }

    # ── Profile / 权限 ──
    if case_id == "D-01":
        return {
            "id": _automation_id(case_id),
            "method": "GET",
            "path": "/api/auth/profile",
            "expect_status": 200,
        }
    if case_id == "D-02":
        return {
            "id": _automation_id(case_id),
            "method": "GET",
            "path": "/api/auth/profile",
            "no_auth": True,
            "expect_status": 401,
        }
    if case_id == "D-03":
        return {
            "id": _automation_id(case_id),
            "method": "GET",
            "path": "/api/auth/profile",
            "no_auth": True,
            "headers": {"Authorization": "Bearer invalid.token.here"},
            "expect_status": 401,
        }
    if case_id == "D-04":
        return {
            "id": _automation_id(case_id),
            "method": "GET",
            "path": "/api/user/me",
            "expect_status": [200, 404],
            "review_required": True,
        }
    if case_id == "P-01":
        return {
            "id": _automation_id(case_id),
            "method": "GET",
            "path": "/api/auth/profile",
            "expect_status": 200,
            "expect_json_subset": {"role": "admin"},
        }

    # 主流程 F-01 → scenario
    if case_id == "F-01":
        return None

    # 兜底：从步骤里抽 method/path
    pm = HTTP_PATH.search(blob)
    if not pm:
        return None
    auto: dict[str, Any] = {
        "id": _automation_id(case_id),
        "method": pm.group("method").upper(),
        "path": pm.group("path"),
        "expect_status": expect,
        "name": f"{case_id} {title}",
    }
    if auto["method"] in ("POST", "PUT", "PATCH"):
        auto["no_auth"] = True
        auto.setdefault("json_body", {})
    if isinstance(expect, list) or (isinstance(expect, int) and expect >= 400):
        auto["review_required"] = True
    return auto


def build_scenario_f01() -> dict[str, Any]:
    flow_user = f"buyer_f01_{uuid.uuid4().hex[:8]}"
    flow_email = f"{flow_user}@test.com"
    return {
        "name": "F-01 注册登录查 Profile",
        "steps": [
            {
                "method": "POST",
                "path": "/api/auth/register",
                "no_auth": True,
                "json_body": {
                    "username": flow_user,
                    "password": "pass1234",
                    "email": flow_email,
                },
                "expect_status": 201,
            },
            {
                "method": "POST",
                "path": "/api/auth/login",
                "no_auth": True,
                "json_body": {
                    "username": flow_user,
                    "password": "pass1234",
                },
                "expect_status": 200,
                "save_token": True,
            },
            {
                "method": "GET",
                "path": "/api/auth/profile",
                "expect_status": 200,
            },
        ],
    }


def md_to_cases_json(
    text: str,
    *,
    base_url: str,
    priority_filter: set[str] | None,
) -> dict[str, Any]:
    review = parse_review_table(text)
    parsed = parse_api_cases(text)
    cases_out: list[dict[str, Any]] = []
    scenarios: list[dict[str, Any]] = []

    if priority_filter is None or "P0" in priority_filter:
        scenarios.append(build_scenario_f01())

    for raw in parsed:
        cid = raw["case_id"]
        meta = review.get(cid, {})
        pri = meta.get("priority", "P2")
        if priority_filter and pri not in priority_filter:
            continue
        auto = build_automation(cid, raw["title"], raw["steps"])
        if auto is None:
            continue
        layer = _layer_for(cid, auto.get("expect_status", 200))
        if pri in ("P2", "P3") and layer in ("E", "X") and not auto.get("review_required"):
            auto["review_required"] = True
        entry: dict[str, Any] = {
            "name": f"{cid} {raw['title']}",
            "layer": layer,
            "priority": pri,
            "automation": auto,
        }
        cases_out.append(entry)

    return {
        "base_url": base_url,
        "setup": "test_init",
        "auth": {
            "type": "bearer_login",
            "login_path": "/api/auth/login",
            "username_field": "username",
            "password_field": "password",
            "username_env": "TEST_USERNAME",
            "password_env": "TEST_PASSWORD",
            "token_json_paths": ["access_token", "token", "data.access_token", "data.token"],
        },
        "cases": cases_out,
        "scenarios": scenarios,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", type=Path, required=True, help="*_testcases.md")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 api_pytest spec .md")
    ap.add_argument("--json-out", type=Path, help="可选：中间 cases JSON")
    ap.add_argument("--base-url", default="http://127.0.0.1:5001")
    ap.add_argument("--priority", default="P0,P1,P2", help="逗号分隔，如 P0,P1")
    ap.add_argument("--title", default="秒杀财务 API（来自功能用例）")
    args = ap.parse_args()

    md_path = _resolve(args.input)
    out_spec = _resolve(args.output)
    text = md_path.read_text(encoding="utf-8")
    pri_set = {p.strip() for p in args.priority.split(",") if p.strip()}

    draft = md_to_cases_json(text, base_url=args.base_url, priority_filter=pri_set)
    if not draft["cases"] and not draft["scenarios"]:
        print("未映射到任何 API automation 用例", file=sys.stderr)
        return 1

    json_path = _resolve(args.json_out) if args.json_out else out_spec.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 cases JSON: {json_path} ({len(draft['cases'])} cases, {len(draft['scenarios'])} scenarios)")

    cmd = [
        sys.executable,
        str(CODEGEN / "testcase_to_api_spec.py"),
        "-i",
        str(json_path),
        "-o",
        str(out_spec),
        "--title",
        args.title,
    ]
    subprocess.run(cmd, check=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = out_spec.read_text(encoding="utf-8")
    if "---" in body:
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[0] + "---" + parts[1] + "---\n\n" + f"> 由 `md_cases_to_api_spec.py` 于 {stamp} 自 `{md_path.name}` 生成\n\n" + parts[2].lstrip("\n")
            out_spec.write_text(body, encoding="utf-8")

    print(f"已写入 spec: {out_spec}")
    print(f"下一步: ./generate.sh \"{out_spec.relative_to(ROOT)}\" --report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
