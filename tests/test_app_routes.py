"""Flask 路由契约测试 —— /success 白名单、/translate JSON 契约、/api/llm-models 形状。

全程 monkeypatch 掉真实翻译函数与 socketio.emit，不打任何 API，不落仓库文件
（UPLOAD/OUTPUT 指向临时目录）。
"""
import io
import os

import pytest

import app as app_module
import config


@pytest.fixture
def client(monkeypatch, tmp_path):
    """隔离的 test client：临时上传/输出目录 + 静默 socketio/sleep。"""
    upload = tmp_path / "uploads"
    output = tmp_path / "output"
    upload.mkdir()
    output.mkdir()
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(upload))
    monkeypatch.setattr(app_module, "OUTPUT_FOLDER", str(output))
    # 进度事件与收尾等待在测试里都无意义，置空加速并避免真实广播
    monkeypatch.setattr(app_module.socketio, "emit", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "sleep", lambda *a, **k: None)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


# ---------------- /success 白名单 ----------------

@pytest.mark.parametrize("bad_value", [
    "javascript:alert(1)",              # XSS URI
    "https://evil.com/x.zip",           # 外链跳转
    "//evil.com/x.zip",                 # 协议相对外链
    "/output/../../etc/passwd.zip",     # 路径穿越
    "/output/x.zip\n/output/y.zip",     # 换行注入
    "/etc/passwd",                      # 非 /output 目录
    "/output/x.txt",                    # 非 .zip
    "",                                 # 空值
])
def test_success_rejects_malicious_zip_path(client, bad_value):
    resp = client.get("/success", query_string={"zip_path": bad_value})
    assert resp.status_code == 302  # 重定向回首页


def test_success_accepts_legit_zip_path(client):
    resp = client.get(
        "/success", query_string={"zip_path": "/output/translations_strings_20260718_abcd1234.zip"}
    )
    assert resp.status_code == 200


# ---------------- /translate JSON 契约 ----------------

def _post_translate(client, filename="strings.json", content=b'{"a":"b"}', **form):
    data = {"file": (io.BytesIO(content), filename)}
    data.update(form)
    return client.post("/translate", data=data, content_type="multipart/form-data")


def test_translate_bad_extension_returns_400_json(client):
    resp = _post_translate(client, filename="notes.txt", content=b"hello", languages="es")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body is not None and body["success"] is False
    assert body.get("error")


def test_translate_no_language_returns_400_json(client):
    resp = _post_translate(client)  # 无 languages 字段
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert body.get("error")


def test_translate_unknown_model_returns_400_json(client):
    resp = _post_translate(
        client, languages="es", translation_engine="openrouter", ai_model="nonexistent/model-x"
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "nonexistent/model-x" in body["error"]


def test_translate_invalid_engine_returns_400_json(client):
    resp = _post_translate(client, languages="es", translation_engine="bogus")
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_translate_empty_model_falls_back_to_default(client, monkeypatch):
    """空 ai_model 应落回 config.DEFAULT_MODEL（捕获传入 translate_single_file 的实参断言）。"""
    captured = {}

    def fake_translate_single_file(file_path, target_language, engine, ai_model, output_dir, cb=None):
        captured["ai_model"] = ai_model
        captured["engine"] = engine
        out_name = f"out_{target_language}.json"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("{}")
        return out_name, out_path

    monkeypatch.setattr(app_module, "translate_single_file", fake_translate_single_file)
    # create_zip 只需产出一个占位 zip 文件，避免依赖真实打包
    monkeypatch.setattr(app_module, "create_zip", lambda files, out: open(out, "w").close())

    resp = _post_translate(
        client, languages="es", translation_engine="openrouter", ai_model=""
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["zip_path"].startswith("/output/") and body["zip_path"].endswith(".zip")
    assert body["redirect_url"].startswith("/success?zip_path=/output/")
    assert captured["ai_model"] == config.DEFAULT_MODEL


def test_translate_partial_failure_returns_errors_array(client, monkeypatch):
    """部分语言失败仍算成功，成功响应带 errors 数组。"""
    def fake_translate_single_file(file_path, target_language, engine, ai_model, output_dir, cb=None):
        if target_language == "fr":
            raise RuntimeError("模拟 fr 翻译失败")
        out_name = f"out_{target_language}.json"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("{}")
        return out_name, out_path

    monkeypatch.setattr(app_module, "translate_single_file", fake_translate_single_file)
    monkeypatch.setattr(app_module, "create_zip", lambda files, out: open(out, "w").close())

    data = {
        "file": (io.BytesIO(b'{"a":"b"}'), "strings.json"),
        "languages": ["es", "fr"],
        "translation_engine": "openrouter",
        "ai_model": config.DEFAULT_MODEL,
    }
    resp = client.post("/translate", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert "errors" in body and any("fr" in e for e in body["errors"])


def test_translate_all_failure_returns_500_json(client, monkeypatch):
    """所有语言都失败 → 500，success:false（不得让前端误判成功）。"""
    def always_fail(*a, **k):
        raise RuntimeError("模拟全部失败")

    monkeypatch.setattr(app_module, "translate_single_file", always_fail)

    resp = _post_translate(
        client, languages="es", translation_engine="openrouter", ai_model=config.DEFAULT_MODEL
    )
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False
    assert body.get("error")


# ---------------- /api/llm-models 形状 ----------------

def test_llm_models_shape(client):
    resp = client.get("/api/llm-models")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    models = body["models"]
    assert isinstance(models, list) and models
    for m in models:
        assert "id" in m and "name" in m and "description" in m and "default" in m
    # 恰有一个（至少一个）默认模型
    assert any(m["default"] for m in models)
