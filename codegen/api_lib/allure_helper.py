"""Allure 报告辅助：无 allure 时降级为 no-op。"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

try:
    import allure

    _HAS_ALLURE = True
except ImportError:  # pragma: no cover
    allure = None  # type: ignore[misc, assignment]
    _HAS_ALLURE = False

LAYER_NAMES: dict[str, str] = {
    "H": "主路径",
    "X": "异常/缺失",
    "E": "边界值",
}

TEST_TYPE_LABELS: dict[str, str] = {
    "api": "API 接口",
    "ui": "UI 界面",
}


def allure_enabled() -> bool:
    return _HAS_ALLURE


def infer_business_from_path(path: str) -> str | None:
    """从脚本/spec 文件名推断业务域。"""
    stem = Pathish(path).stem.lower()
    if any(k in stem for k in ("seckill", "api_smoke", "seckill_api", "imported_api", "imported_smoke")):
        return "秒杀财务系统"
    if "api_smoke" in stem or stem.endswith("_smoke"):
        return "API 冒烟"
    return None


class Pathish:
    """轻量路径包装，避免 pathlib 循环依赖测试场景。"""

    def __init__(self, raw: str) -> None:
        self.stem = os.path.splitext(os.path.basename(raw.replace("\\", "/")))[0]


def _marker_arg(item: Any, name: str) -> str | None:
    marker = item.get_closest_marker(name)
    if marker is None or not marker.args:
        return None
    val = str(marker.args[0]).strip()
    return val or None


def infer_layer_from_nodeid(nodeid: str) -> str | None:
    fn = nodeid.split("::")[-1].lower()
    if fn.startswith("test_ui_") or fn.startswith("test_scenario_ui_"):
        return "H"
    if "prd_c" in fn or "_x_" in fn or "no_auth" in fn or "invalid_body" in fn:
        return "X"
    if "_e_" in fn:
        return "E"
    if fn.startswith("test_tc_seckill_prd"):
        return "X"
    if fn.startswith("test_tc_"):
        return "H"
    return None


def apply_report_labels(item: Any) -> None:
    """pytest 用例启动时写入 Allure 业务维度：test_type / business / layer。"""
    if not _HAS_ALLURE:
        return

    test_type = os.environ.get("ALLURE_TEST_TYPE", "").strip().lower()
    business = os.environ.get("ALLURE_BUSINESS", "").strip()
    if not business:
        inferred = infer_business_from_path(item.fspath.strpath if hasattr(item, "fspath") else item.nodeid)
        if inferred:
            business = inferred

    if test_type:
        label = TEST_TYPE_LABELS.get(test_type, test_type.upper())
        allure.dynamic.label("test_type", label)
        allure.dynamic.tag(test_type.upper())

    if business:
        allure.dynamic.epic(business)
        allure.dynamic.label("business", business)

    layer = _marker_arg(item, "allure_layer") or infer_layer_from_nodeid(item.nodeid)
    if layer:
        layer_u = layer.upper()
        layer_name = LAYER_NAMES.get(layer_u, layer_u)
        allure.dynamic.feature(f"{layer_u} · {layer_name}")
        allure.dynamic.label("layer", layer_u)

    priority = _marker_arg(item, "allure_priority")
    if priority:
        allure.dynamic.label("priority", priority)

    story = _marker_arg(item, "allure_story")
    if not story:
        doc = getattr(item.function, "__doc__", "") or ""
        story = doc.strip().split("\n")[0][:120] if doc.strip() else None
    if story:
        allure.dynamic.story(story)


def allure_api_detail_enabled() -> bool:
    if not _HAS_ALLURE:
        return False
    v = os.environ.get("ALLURE_API_DETAIL", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


_SENSITIVE_HEADER_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-access-token",
        "x-auth-token",
        "proxy-authorization",
    }
)
_SENSITIVE_BODY_KEYS = frozenset({"password", "token", "access_token", "refresh_token", "secret"})


def _redact_mapping(data: Any) -> Any:
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            key = str(k).lower()
            if key in _SENSITIVE_HEADER_KEYS or key in _SENSITIVE_BODY_KEYS:
                out[k] = "***"
            else:
                out[k] = _redact_mapping(v)
        return out
    if isinstance(data, list):
        return [_redact_mapping(x) for x in data]
    return data


def _truncate_text(text: str, *, limit: int | None = None) -> str:
    max_len = limit if limit is not None else int(os.environ.get("ALLURE_API_BODY_MAX", "12000"))
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n…（已截断，共 {len(text)} 字符）"


def attach_http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: Any = None,
    json_body: Any = None,
) -> None:
    if not allure_api_detail_enabled():
        return
    payload: dict[str, Any] = {
        "method": method.upper(),
        "url": url,
    }
    if params:
        payload["query"] = _redact_mapping(params)
    if json_body is not None:
        payload["body"] = _redact_mapping(json_body)
    if headers:
        payload["headers"] = _redact_mapping(dict(headers))
    attach_json("请求", payload)


def attach_http_response(response: Any, *, elapsed_sec: float) -> None:
    if not allure_api_detail_enabled():
        return
    payload: dict[str, Any] = {
        "status_code": getattr(response, "status_code", None),
        "elapsed_ms": round(elapsed_sec * 1000, 2),
    }
    resp_headers = getattr(response, "headers", None)
    if resp_headers is not None:
        payload["headers"] = _redact_mapping(dict(resp_headers))
    text = getattr(response, "text", "") or ""
    try:
        body = response.json()
        payload["body"] = _redact_mapping(body)
    except Exception:
        payload["body_text"] = _truncate_text(text)
    attach_json("响应", payload)


@contextmanager
def report_step(title: str) -> Iterator[None]:
    if _HAS_ALLURE:
        with allure.step(title):
            yield
    else:
        yield


def attach_json(name: str, data: Any) -> None:
    if not _HAS_ALLURE:
        return
    allure.attach(
        json.dumps(data, ensure_ascii=False, indent=2),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def attach_text(name: str, text: str) -> None:
    if not _HAS_ALLURE or not text:
        return
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)


def attach_png(name: str, body: bytes) -> None:
    if not _HAS_ALLURE or not body:
        return
    allure.attach(body, name=name, attachment_type=allure.attachment_type.PNG)


def attach_page_screenshot(page: Any, *, name: str = "页面截图") -> None:
    if not _HAS_ALLURE or os.environ.get("ALLURE_UI_SCREENSHOT", "1").strip().lower() in ("0", "false", "no"):
        return
    try:
        png = page.screenshot(full_page=False)
        attach_png(name, png)
    except Exception:
        pass
