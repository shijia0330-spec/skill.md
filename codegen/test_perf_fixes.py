"""压测相关 codegen 单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "codegen"))

from run_spec import _jmeter_resolve_header_value  # noqa: E402


def test_jmeter_resolve_header_value_uses_property():
    assert _jmeter_resolve_header_value("Bearer ${PERF_ACCESS_TOKEN}") == (
        "Bearer ${__P(PERF_ACCESS_TOKEN)}"
    )
    assert _jmeter_resolve_header_value("Bearer ${PERF_ACCESS_TOKEN}") == (
        "Bearer ${__P(PERF_ACCESS_TOKEN)}"
    )
    assert _jmeter_resolve_header_value("tid=${PERF_TENANT_ID}") == (
        "tid=${__P(PERF_TENANT_ID,1)}"
    )


@patch("fetch_perf_token.HealingSession")
def test_fetch_token_retries_without_storage_state(mock_session_cls):
    from fetch_perf_token import fetch_token_ui

    session = MagicMock()
    mock_session_cls.return_value = session
    session.headers = {"Authorization": "Bearer good-token"}

    probe_results = [False, True]

    def probe_side_effect(_session, _base, _path):
        return probe_results.pop(0)

    with patch("fetch_perf_token._probe_rest", side_effect=probe_side_effect):
        token, _tenant = fetch_token_ui(
            "http://your-server:5001",
            {"type": "ui_storage_login", "storage_state": "output/.auth/x.json", "probe_path": "/api/health"},
            "/api/health",
        )

    assert token == "good-token"
    assert session.configure_ui_storage_login.call_count == 2
