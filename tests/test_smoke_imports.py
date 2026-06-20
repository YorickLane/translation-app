"""导入冒烟测试 —— 每个生产模块能干净 import。

作用: 删死代码 / 重构后，任何模块的悬空 import 或语法错会在这里立刻暴露，
而不必启动 Web app 才发现。
"""
import importlib

import pytest

MODULES = [
    "config",
    "translation_config",
    "translation_postprocess",
    "js_locale",
    "llm_models",
    "llm_client",
    "cost_estimator",
    "translate",
    "translate_llm",
    "translation_runner",
    "cli",
    "app",
    "check_translation_quality",
    "split_json",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    assert importlib.import_module(name) is not None
