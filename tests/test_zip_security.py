"""extract_zip_files 安全测试 —— 手工构造恶意 ZIP，断言穿越/绝对路径/符号链接/ZIP 炸弹
被跳过或抛错，且 extract_dir 之外不产生任何文件；正常 ZIP 正确解出。
"""
import os
import stat
import zipfile

import pytest

import app as app_module
from app import extract_zip_files


def _make_zip(path, entries):
    """entries: [(arcname 或 ZipInfo, data_str), ...]。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, data in entries:
            zf.writestr(arc, data)


def _extract_dir(tmp_path):
    d = tmp_path / "extract"
    d.mkdir()
    return d


def _rel_names(valid):
    return [rel for rel, _ in valid]


# ---------------- 正常 ZIP ----------------

def test_normal_zip_extracts_valid_files(tmp_path):
    zip_path = tmp_path / "good.zip"
    _make_zip(zip_path, [
        ("a.json", '{"k":"v"}'),
        ("sub/b.js", "export default {}"),
        ("readme.txt", "ignore me"),        # 非翻译文件，不收集
        ("__MACOSX/foo.json", "junk"),      # macOS 资源，跳过
    ])
    extract_dir = _extract_dir(tmp_path)

    valid = extract_zip_files(str(zip_path), str(extract_dir))

    assert sorted(_rel_names(valid)) == ["a.json", "sub/b.js"]
    real_root = os.path.realpath(str(extract_dir)) + os.sep
    for _rel, absp in valid:
        assert os.path.isfile(absp)
        assert os.path.realpath(absp).startswith(real_root)
    # __MACOSX 条目不应被解压
    assert not os.path.exists(os.path.join(str(extract_dir), "__MACOSX", "foo.json"))


# ---------------- 路径穿越 ----------------

def test_path_traversal_entry_skipped(tmp_path):
    zip_path = tmp_path / "evil.zip"
    _make_zip(zip_path, [
        ("../evil.json", '{"x":"y"}'),
        ("ok.json", '{"a":"b"}'),
    ])
    extract_dir = _extract_dir(tmp_path)

    valid = extract_zip_files(str(zip_path), str(extract_dir))

    assert _rel_names(valid) == ["ok.json"]
    # 穿越目标（extract_dir 的父目录）绝不产生文件
    assert not os.path.exists(str(tmp_path / "evil.json"))


# ---------------- 绝对路径 ----------------

def test_absolute_path_entry_skipped(tmp_path):
    zip_path = tmp_path / "abs.zip"
    info = zipfile.ZipInfo("/abs_evil.json")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(info, '{"x":"y"}')
        zf.writestr("ok.json", '{"a":"b"}')
    extract_dir = _extract_dir(tmp_path)

    valid = extract_zip_files(str(zip_path), str(extract_dir))

    assert _rel_names(valid) == ["ok.json"]
    # 绝对路径条目不得命中宿主机文件系统根
    assert not os.path.exists("/abs_evil.json")


# ---------------- 符号链接 ----------------

def test_symlink_entry_rejected(tmp_path):
    zip_path = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link.json")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16  # 标记为符号链接
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(info, "/etc/passwd")  # 链接目标
        zf.writestr("ok.json", '{"a":"b"}')
    extract_dir = _extract_dir(tmp_path)

    valid = extract_zip_files(str(zip_path), str(extract_dir))

    assert _rel_names(valid) == ["ok.json"]
    # 符号链接条目不得落地（lexists 也检测悬空链接）
    assert not os.path.lexists(os.path.join(str(extract_dir), "link.json"))


# ---------------- ZIP 炸弹：解压后总大小 ----------------

def test_zip_bomb_total_size_rejected(tmp_path, monkeypatch):
    zip_path = tmp_path / "bomb.zip"
    _make_zip(zip_path, [("big.json", "A" * 5000)])  # file_size=5000
    extract_dir = _extract_dir(tmp_path)

    monkeypatch.setattr(app_module, "_ZIP_MAX_TOTAL_UNCOMPRESSED", 100)
    with pytest.raises(ValueError):
        extract_zip_files(str(zip_path), str(extract_dir))


# ---------------- ZIP 炸弹：条目数 ----------------

def test_zip_bomb_entry_count_rejected(tmp_path, monkeypatch):
    zip_path = tmp_path / "many.zip"
    _make_zip(zip_path, [("a.json", "{}"), ("b.json", "{}"), ("c.json", "{}")])
    extract_dir = _extract_dir(tmp_path)

    monkeypatch.setattr(app_module, "_ZIP_MAX_ENTRIES", 2)
    with pytest.raises(ValueError):
        extract_zip_files(str(zip_path), str(extract_dir))


# ---------------- ZIP 炸弹：单成员高压缩比 ----------------

def test_high_compression_ratio_member_skipped(tmp_path, monkeypatch):
    zip_path = tmp_path / "ratio.zip"
    # 20000 个 'A' 压缩后约 37 字节，比率 ~540 > 100
    _make_zip(zip_path, [("huge.json", "A" * 20000), ("ok.json", '{"a":"b"}')])
    extract_dir = _extract_dir(tmp_path)

    # 把单成员体积阈值降到 1KB，让 huge.json 命中压缩比检查
    monkeypatch.setattr(app_module, "_ZIP_RATIO_CHECK_MIN_SIZE", 1024)
    valid = extract_zip_files(str(zip_path), str(extract_dir))

    assert _rel_names(valid) == ["ok.json"]
    assert not os.path.exists(os.path.join(str(extract_dir), "huge.json"))
