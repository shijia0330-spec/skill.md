"""verify_all 专用：故意失败，验证 conftest 进度报告 + 缺陷草稿钩子。"""
from __future__ import annotations

import pytest


def test_hook_verify_intentional_fail() -> None:
    pytest.fail("verify_all conftest hook smoke — 预期失败")
