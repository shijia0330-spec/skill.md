"""Appium 移动端 codegen 辅助库。"""
from .locator_healer import click_with_heal, find_with_heal
from .selector_registry import merge_registry_step, record_healed_locator, resolve_l0_attempt

__all__ = [
    "click_with_heal",
    "find_with_heal",
    "merge_registry_step",
    "record_healed_locator",
    "resolve_l0_attempt",
]
