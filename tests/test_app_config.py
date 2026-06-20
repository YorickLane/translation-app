"""app 文件类型校验 —— ALLOWED_EXTENSIONS 单源真相 + allowed_file 行为守护。"""
import app
import config


def test_allowed_extensions_single_source():
    """app 与 config 的 ALLOWED_EXTENSIONS 必须同源（同一对象，SoT），且含 zip。"""
    assert app.ALLOWED_EXTENSIONS is config.ALLOWED_EXTENSIONS
    assert "zip" in config.ALLOWED_EXTENSIONS


def test_allowed_file_accepts_supported_rejects_others():
    assert app.allowed_file("x.json") is True
    assert app.allowed_file("x.js") is True
    assert app.allowed_file("strings.zip") is True
    assert app.allowed_file("x.txt") is False
    assert app.allowed_file("noext") is False


def test_max_content_length_wired_to_50mb():
    """D4: MAX_FILE_SIZE 已接线为 Flask MAX_CONTENT_LENGTH，上限 50MB。"""
    assert config.MAX_FILE_SIZE == 50 * 1024 * 1024
    assert app.app.config["MAX_CONTENT_LENGTH"] == config.MAX_FILE_SIZE
