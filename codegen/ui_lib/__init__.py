"""UI 测试运行时库 — 由 run_spec.py 生成的 pytest 调用。"""
from __future__ import annotations

from .artifacts import artifacts_dir, save_failure_artifacts, safe_stem
from .auth import ensure_logged_in, is_login_url, run_ensure_logged_in_step
from .batch import run_ui_batch, run_ui_batch_async
from .context import UIContext
from .element_ui import click_radio, expect_form_error, expect_radio_checked, run_click_radio_step
from .env_check import repair_deps_hints, run_repair_deps, validate_script
from .heal_kb import UIHealKB
from .locator_resolver import (
    LocatorResolutionError,
    ResolveMeta,
    build_locator_strategies,
    click_with_healing,
    fill_with_healing,
    get_locator,
)
from .nl_parser import parse_nl, parse_nl_to_flow
from .nl_runner import execute_nl, parse_only
from .pretest import assert_readiness, check_readiness
from .retry import retry_step
from .runner import run_ui_expects, run_ui_flow, run_ui_step
from .scopes import resolve_scope
from .worker import run_flow_in_worker

__all__ = [
    "UIContext",
    "LocatorResolutionError",
    "ResolveMeta",
    "assert_readiness",
    "artifacts_dir",
    "build_locator_strategies",
    "check_readiness",
    "click_radio",
    "click_with_healing",
    "ensure_logged_in",
    "execute_nl",
    "expect_form_error",
    "expect_radio_checked",
    "fill_with_healing",
    "get_locator",
    "is_login_url",
    "parse_nl",
    "parse_nl_to_flow",
    "parse_only",
    "repair_deps_hints",
    "resolve_scope",
    "retry_step",
    "run_click_radio_step",
    "run_ensure_logged_in_step",
    "run_flow_in_worker",
    "run_repair_deps",
    "run_ui_batch",
    "run_ui_batch_async",
    "run_ui_expects",
    "run_ui_flow",
    "run_ui_step",
    "safe_stem",
    "save_failure_artifacts",
    "validate_script",
]
