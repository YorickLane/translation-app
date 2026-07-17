"""LLM 引擎嵌套 JSON 展平/重建回归 —— monkeypatch translate_batch，不打真 API。

覆盖 translate_llm._flatten / _rebuild / _path_to_str 与 translate_json_file_llm 的
嵌套处理：多层 dict、含 list、非字符串叶子、顶层为 list、深层混合，并断言送去翻译的
字符串集合恰好等于全部非空 str 叶子。

用 target_language="en" 跑结构相关用例：en 不触发英文混入检测 / 罗曼语系小写 / QA 回灌，
str.upper 变换能原样体现，便于精确断言结构与键序。
"""
import json

import pytest

import translate_llm


@pytest.fixture
def upper_engine(monkeypatch):
    """把 translate_batch 换成确定性 str.upper，并记录所有送翻译的字符串。"""
    sent = []

    def fake_translate_batch(values, **kwargs):
        sent.extend(values)
        return [v.upper() for v in values]

    monkeypatch.setattr(translate_llm, "translate_batch", fake_translate_batch)
    return sent


def _run(tmp_path, data, lang="en"):
    """写入 data → translate_json_file_llm → 读回输出 JSON。"""
    src = tmp_path / "s.json"
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out_name = translate_llm.translate_json_file_llm(str(src), lang, None, "m", str(tmp_path))
    return json.loads((tmp_path / out_name).read_text(encoding="utf-8"))


# ---------- 纯函数：_flatten / _rebuild / _path_to_str ----------

def test_flatten_collects_only_nonempty_str_leaves():
    data = {
        "a": "hello",
        "b": {"c": "world", "d": 3},
        "e": ["x", "", 7, "y"],
        "f": "",
        "g": None,
        "h": True,
        "i": 1.5,
    }
    leaves = translate_llm._flatten(data)
    # 只收集非空 str 叶子；顺序为文档序；list 下标进 path
    assert leaves == [
        (("a",), "hello"),
        (("b", "c"), "world"),
        (("e", 0), "x"),
        (("e", 3), "y"),
    ]


def test_rebuild_preserves_structure_and_key_order():
    data = {"z": "a", "y": {"x": "b", "w": 2}, "v": ["c"]}
    translations = {("z",): "A", ("y", "x"): "B", ("v", 0): "C"}
    rebuilt = translate_llm._rebuild(data, translations)
    # json.dumps 保序 → 同时断言结构、键序、值替换；未翻译的 w=2 原样
    assert json.dumps(rebuilt, ensure_ascii=False) == json.dumps(
        {"z": "A", "y": {"x": "B", "w": 2}, "v": ["C"]}, ensure_ascii=False
    )


def test_rebuild_keeps_untranslated_and_scalar_leaves():
    data = {"a": "keep", "b": 3, "c": None, "d": ""}
    rebuilt = translate_llm._rebuild(data, {})  # 无任何译文
    assert json.dumps(rebuilt, ensure_ascii=False) == json.dumps(data, ensure_ascii=False)


def test_path_to_str_formats_list_index():
    assert translate_llm._path_to_str(("a", "b")) == "a.b"
    assert translate_llm._path_to_str(("items", 0, "label")) == "items[0].label"
    assert translate_llm._path_to_str((0,)) == "[0]"
    assert translate_llm._path_to_str((0, "label")) == "[0].label"


# ---------- 集成：translate_json_file_llm ----------

def test_nested_dict_structure_and_order_preserved(tmp_path, upper_engine):
    data = {
        "title": "home",
        "menu": {
            "file": "open",
            "edit": {"undo": "back", "redo": "forward"},
        },
        "footer": "bye",
    }
    result = _run(tmp_path, data)
    expected = {
        "title": "HOME",
        "menu": {
            "file": "OPEN",
            "edit": {"undo": "BACK", "redo": "FORWARD"},
        },
        "footer": "BYE",
    }
    # json.dumps 保序 → 一次性断言结构、键序、值
    assert json.dumps(result, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)
    assert set(upper_engine) == {"home", "open", "back", "forward", "bye"}


def test_list_of_strings_translated_positions_kept(tmp_path, upper_engine):
    data = {"tags": ["red", "green", "blue"], "name": "palette"}
    result = _run(tmp_path, data)
    expected = {"tags": ["RED", "GREEN", "BLUE"], "name": "PALETTE"}
    assert json.dumps(result, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)
    assert set(upper_engine) == {"red", "green", "blue", "palette"}


def test_non_string_leaves_preserved(tmp_path, upper_engine):
    data = {
        "count": 42,
        "ratio": 3.14,
        "enabled": True,
        "disabled": False,
        "missing": None,
        "empty": "",
        "label": "go",
    }
    result = _run(tmp_path, data)
    expected = {
        "count": 42,
        "ratio": 3.14,
        "enabled": True,
        "disabled": False,
        "missing": None,
        "empty": "",
        "label": "GO",
    }
    # 数字/bool/null/空串原样，仅非空 str 叶子被翻译
    assert json.dumps(result, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)
    assert set(upper_engine) == {"go"}


def test_top_level_list(tmp_path, upper_engine):
    data = ["alpha", "beta", 5, "", {"k": "gamma"}]
    result = _run(tmp_path, data)
    expected = ["ALPHA", "BETA", 5, "", {"k": "GAMMA"}]
    assert json.dumps(result, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)
    assert set(upper_engine) == {"alpha", "beta", "gamma"}


def test_deep_mixed_nesting(tmp_path, upper_engine):
    data = {
        "sections": [
            {
                "heading": "intro",
                "items": ["first", 1, {"note": "deep"}],
            },
            {
                "heading": "outro",
                "items": [],
            },
        ],
        "meta": {"version": 2, "author": "me", "tags": ["a", "b"]},
    }
    result = _run(tmp_path, data)
    expected = {
        "sections": [
            {
                "heading": "INTRO",
                "items": ["FIRST", 1, {"note": "DEEP"}],
            },
            {
                "heading": "OUTRO",
                "items": [],
            },
        ],
        "meta": {"version": 2, "author": "ME", "tags": ["A", "B"]},
    }
    assert json.dumps(result, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)
    assert set(upper_engine) == {"intro", "first", "deep", "outro", "me", "a", "b"}


def test_sent_strings_equal_all_nonempty_str_leaves(tmp_path, upper_engine):
    """核心不变量：送翻译的字符串集合 == 全部非空 str 叶子（不多不少）。"""
    data = {
        "a": "one",
        "b": {"c": "two", "d": ["three", "", 9, "four"]},
        "e": "",
        "f": 3,
        "g": None,
        "h": [{"i": "five"}, "six"],
    }
    _run(tmp_path, data)
    expected_leaves = {v for _, v in translate_llm._flatten(data)}
    assert set(upper_engine) == expected_leaves
    assert expected_leaves == {"one", "two", "three", "four", "five", "six"}


def test_needs_review_sidecar_uses_dot_path(tmp_path, monkeypatch):
    """嵌套/数组路径进 needs_review 时，key 用点号路径（数组下标 [i]）。"""
    data = {"menu": {"save": "确认"}, "items": ["取消"]}
    src = tmp_path / "s.json"
    src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    # 让所有译文残留小写拉丁 'abc'：过 batch 级 >20% 关键词阈值（不触发 sleep），
    # 但被 item 级 contains_english 判未翻译 → 进 QA 闭环 → sidecar。
    monkeypatch.setattr(
        translate_llm, "translate_with_llm",
        lambda items, lang, model: {k: "abc" for k in items},
    )
    out_name = translate_llm.translate_json_file_llm(str(src), "zh-TW", None, "m", str(tmp_path))
    review = tmp_path / out_name.replace(".json", ".needs_review.json")
    assert review.exists()
    entries = json.loads(review.read_text(encoding="utf-8"))
    assert {e["key"] for e in entries} == {"menu.save", "items[0]"}
    assert all(e["reason"] == "英文未翻译" for e in entries)
