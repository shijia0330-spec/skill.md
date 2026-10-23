"""API 测试运行时库 — 由 run_spec.py 生成的 pytest 调用。"""
from __future__ import annotations

from .assertions import ASSERTION_REGISTRY, run_assertions, run_legacy_assertions
from .batch import load_data_rows, merge_case_with_data_row, run_batch, run_batch_async, topological_sort
from .data_factory_hook import run_data_factory_spec
from .json_path import extract_by_path
from .executor import run_case, run_scenario, run_step
from .setup_hook import parse_api_setup, run_api_setup
from .token_utils import DEFAULT_TOKEN_PATHS, extract_token
from .heal_kb import HealKB
from .http_client import HealingSession, create_anon_session, create_api_session
from .refs_registry import RefsRegistry
from .resolver import fill_body, resolve_env, resolve_string
from .variable_pool import VariablePool

__all__ = [
    "ASSERTION_REGISTRY",
    "HealKB",
    "HealingSession",
    "RefsRegistry",
    "VariablePool",
    "create_anon_session",
    "create_api_session",
    "extract_by_path",
    "fill_body",
    "load_data_rows",
    "merge_case_with_data_row",
    "parse_api_setup",
    "resolve_env",
    "resolve_string",
    "run_api_setup",
    "run_assertions",
    "run_batch",
    "run_batch_async",
    "run_case",
    "run_data_factory_spec",
    "run_legacy_assertions",
    "run_scenario",
    "run_step",
    "topological_sort",
    "extract_token",
    "DEFAULT_TOKEN_PATHS",
]
