"""data_factory CSV 导出与 JMeter data_source codegen 测试。"""
from __future__ import annotations

import sys
from pathlib import Path

_CODEGEN = Path(__file__).resolve().parent
if str(_CODEGEN) not in sys.path:
    sys.path.insert(0, str(_CODEGEN))

from run_spec import (  # noqa: E402
    parse_frontmatter,
    render_data_factory,
    render_jmeter_script,
)


def test_data_factory_csv_export_and_cleanup_codegen():
    spec_path = _CODEGEN.parent / "templates" / "data_factory.md"
    meta, body = parse_frontmatter(spec_path.read_text(encoding="utf-8"))
    out = render_data_factory(meta, body)
    assert "_extra_cols" in out
    assert "--cleanup" in out
    assert "insert_users" in out
    assert "hash_password" in out
    assert "Test123!" in out
    assert "users.csv" in out


def test_jmeter_csv_data_set_and_token_extractor():
    spec_path = _CODEGEN.parent / "templates" / "jmeter_test.md"
    meta, body = parse_frontmatter(spec_path.read_text(encoding="utf-8"))
    out = render_jmeter_script(meta, body)
    assert "CSVDataSet" in out
    assert "users.csv" in out
    assert "username,password" in out
    assert "ignoreFirstLine\">true" in out
    assert "recycle\">false" in out
    assert "shareMode.thread" in out
    assert "JSONPostProcessor" in out
    assert "Bearer ${token}" in out
    assert "${username}" in out
    assert "${password}" in out
    assert "password_hash" not in out
