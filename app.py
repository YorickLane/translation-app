# app.py

from translate import create_zip, create_zip_with_structure
from translation_runner import translate_single_file
from llm_models import get_models, get_model_info
from cost_estimator import estimate_cost, format_cost_summary
from flask import Flask, request, render_template, send_from_directory, flash, redirect, jsonify
import logging
import re
import stat
from werkzeug.utils import secure_filename
import os
import uuid
import shutil
import zipfile
from functools import lru_cache
from google.cloud import translate_v2 as translate
import datetime
from flask_socketio import SocketIO, emit
from time import sleep
from config import SECRET_KEY, TRANSLATION_ENGINE, ALLOWED_EXTENSIONS
import config
from google.auth.exceptions import RefreshError

app = Flask(__name__)
app.secret_key = SECRET_KEY
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
socketio = SocketIO(app, async_mode='threading')

# Configuration
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
# ALLOWED_EXTENSIONS 单源真相在 config.py（上方 import），勿在此另立副本
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_SIZE  # D4: 上传上限 50MB，超限 → 413

# ZIP 炸弹防护阈值（可被测试 monkeypatch 覆盖）
_ZIP_MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024  # 解压后总大小上限 200MB
_ZIP_MAX_ENTRIES = 2000                          # 条目数上限
_ZIP_MAX_COMPRESSION_RATIO = 100                 # 单成员最大压缩比
_ZIP_RATIO_CHECK_MIN_SIZE = 10 * 1024 * 1024     # 单成员 > 此值才做压缩比检查

# /success 允许的 zip_path 白名单：只放行本机 /output/ 下的 .zip，挡掉 javascript: / 外链 / 路径穿越
_SUCCESS_ZIP_PATH_RE = re.compile(r"^/output/[A-Za-z0-9_.\-]+\.zip$")

# 合法的翻译引擎集合
_VALID_ENGINES = ("google", "openrouter")


class AllTranslationsFailed(Exception):
    """全部语言/文件翻译失败 —— 映射到 HTTP 500（区别于坏输入的 400）。"""


def _emit_progress(data, socket_sid=None):
    """发送进度事件。

    socket_sid 存在时定向发送给发起请求的客户端（前端把 socket.id 放进 FormData）；
    缺失时退回原有全局广播行为（namespace 不变 /test）。
    """
    if socket_sid:
        socketio.emit("progress", data, namespace="/test", to=socket_sid)
    else:
        socketio.emit("progress", data, namespace="/test")


def _safe_remove(path):
    """尽力删除单个文件，失败仅告警不抛错。"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"清理文件失败 {path}: {e}")


def _safe_rmtree(path):
    """尽力删除目录树，失败仅告警不抛错。"""
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path)
    except Exception as e:
        logger.warning(f"清理目录失败 {path}: {e}")

# Google Translate Client —— lazy init，凭证缺失时降级到 fallback 语言列表
# 这样 OpenRouter 引擎路径不受 Google 凭证影响，独立可用
_translate_client = None


def _get_translate_client():
    """查找 Google 凭证并 init client。查找优先级见 config.GOOGLE_CREDENTIALS_FILENAMES。"""
    global _translate_client
    if _translate_client is None:
        from config import GOOGLE_CREDENTIALS_FILENAMES
        # 未显式设 env → 尝试项目根的 fallback 文件 (优先新名字)
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            project_dir = os.path.dirname(os.path.abspath(__file__))
            for fname in GOOGLE_CREDENTIALS_FILENAMES:
                candidate = os.path.join(project_dir, fname)
                if os.path.isfile(candidate):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = candidate
                    break
        # env 仍空时 google-cloud 自动走 gcloud ADC / metadata
        _translate_client = translate.Client()
    return _translate_client


# 无 Google 凭证时的 fallback 语言列表（覆盖常见 UI 翻译场景）
_FALLBACK_LANGUAGES = [
    {"name": "English", "code": "en"},
    {"name": "Chinese (Simplified)", "code": "zh"},
    {"name": "Chinese (Traditional)", "code": "zh-TW"},
    {"name": "Spanish", "code": "es"},
    {"name": "French", "code": "fr"},
    {"name": "German", "code": "de"},
    {"name": "Italian", "code": "it"},
    {"name": "Portuguese", "code": "pt"},
    {"name": "Arabic", "code": "ar"},
    {"name": "Japanese", "code": "ja"},
    {"name": "Korean", "code": "ko"},
    {"name": "Russian", "code": "ru"},
    {"name": "Dutch", "code": "nl"},
    {"name": "Polish", "code": "pl"},
    {"name": "Turkish", "code": "tr"},
    {"name": "Vietnamese", "code": "vi"},
    {"name": "Thai", "code": "th"},
    {"name": "Indonesian", "code": "id"},
    {"name": "Hindi", "code": "hi"},
    {"name": "Malay", "code": "ms"},
]

# Cache setup
LAST_CACHED = datetime.datetime.now()


@lru_cache(maxsize=None)
def get_supported_languages():
    """返回支持的语言列表。有 Google 凭证时拉 Google Translate 全部语言（数量会随 Google 变动），否则返回 20 种 fallback。"""
    try:
        languages = _get_translate_client().get_languages()
        return [{"name": lang["name"], "code": lang["language"]} for lang in languages]
    except FileNotFoundError:
        logger.warning(
            "无 Google 凭证 (未设 GOOGLE_APPLICATION_CREDENTIALS / 无 gcloud ADC / "
            "项目根无 google-credentials.json 或 serviceKey.json)，"
            "使用 fallback 语言列表（20 种常用语言）"
        )
        return _FALLBACK_LANGUAGES
    except RefreshError as e:
        logger.error("Google Translate token refresh 失败: %s", e)
        flash("Google 凭证刷新失败，使用默认语言列表")
        return _FALLBACK_LANGUAGES
    except Exception as e:
        logger.warning(f"Google Translate 客户端初始化失败 ({type(e).__name__})，使用 fallback 语言列表")
        return _FALLBACK_LANGUAGES


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_zip_file(filename):
    """检查文件是否为 ZIP 文件"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "zip"


def extract_zip_files(zip_path, extract_dir):
    """
    安全解压 ZIP 文件，逐成员校验后再解压，递归获取所有有效的 .json/.js 文件。

    防护措施（旧实现的路径穿越检查是死代码，extractall 照解，已彻底重写）：
      - 跳过目录 / __MACOSX / ._ 资源文件
      - 拒绝符号链接成员（防止解压后指向宿主机文件被打包外送）
      - 路径穿越：realpath 后必须落在 extract_dir 内，否则跳过（绝不解压）
      - ZIP 炸弹：解压前预检总大小/条目数；单成员按压缩比拒绝
      - 只对通过全部校验的成员逐个 zf.extract()（不再 extractall）

    返回: [(相对路径, 绝对路径), ...]
    """
    valid_files = []
    real_extract_dir = os.path.realpath(extract_dir)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            infolist = zf.infolist()

            # ZIP 炸弹防护：解压前预检条目数与解压后总大小
            if len(infolist) > _ZIP_MAX_ENTRIES:
                raise ValueError(
                    f"ZIP 条目数过多（{len(infolist)} > {_ZIP_MAX_ENTRIES}），疑似 ZIP 炸弹，已拒绝"
                )
            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > _ZIP_MAX_TOTAL_UNCOMPRESSED:
                raise ValueError(
                    f"ZIP 解压后总大小过大（{total_uncompressed} 字节 > "
                    f"{_ZIP_MAX_TOTAL_UNCOMPRESSED} 字节），疑似 ZIP 炸弹，已拒绝"
                )

            for member in infolist:
                name = member.filename

                # 跳过目录条目
                if name.endswith('/'):
                    continue
                # 跳过 macOS 资源文件
                if name.startswith('__MACOSX') or os.path.basename(name).startswith('._'):
                    continue

                # 拒绝符号链接（external_attr 高 16 位是 unix st_mode）
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    logger.warning(f"跳过符号链接条目: {name}")
                    continue

                # 单成员 ZIP 炸弹：压缩比过高且体积超阈值 → 拒绝该成员
                ratio = member.file_size / max(member.compress_size, 1)
                if ratio > _ZIP_MAX_COMPRESSION_RATIO and member.file_size > _ZIP_RATIO_CHECK_MIN_SIZE:
                    logger.warning(f"跳过高压缩比成员（{ratio:.0f}x, {member.file_size} 字节）: {name}")
                    continue

                # 路径穿越：解析后必须落在 extract_dir 内
                target = os.path.realpath(os.path.join(extract_dir, name))
                if not target.startswith(real_extract_dir + os.sep):
                    logger.warning(f"跳过越界路径条目（疑似路径穿越）: {name}")
                    continue

                # 通过全部校验，逐个解压
                zf.extract(member, extract_dir)

                # 只从通过校验的成员收集有效翻译文件，路径用校验后的 target
                if name.endswith(('.json', '.js')) and os.path.isfile(target):
                    valid_files.append((name, target))
                    logger.info(f"发现有效文件: {name}")

        logger.info(f"ZIP 解压完成，共发现 {len(valid_files)} 个有效文件")
        return valid_files

    except zipfile.BadZipFile:
        logger.error(f"无效的 ZIP 文件: {zip_path}")
        raise ValueError("上传的文件不是有效的 ZIP 压缩包")


@app.route("/", methods=["GET", "POST"])
def upload_form():
    return render_template("upload.html", languages=get_supported_languages())


@app.route("/output/<filename>")
def uploaded_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


@app.route("/success")
def success_page():
    zip_path = request.args.get("zip_path", "")
    # 只放行本机 /output/ 下的 .zip；挡掉 javascript: URI XSS、外链跳转、路径穿越
    if not _SUCCESS_ZIP_PATH_RE.fullmatch(zip_path):
        flash("未找到有效的翻译结果文件")
        return redirect("/")
    return render_template("success.html", zip_path=zip_path)


@app.route("/api/llm-models")
def get_llm_models_api():
    """API 端点：获取可用的 AI 模型列表（OpenRouter 3 档）"""
    try:
        models = get_models()
        return jsonify({"success": True, "models": models})
    except Exception as e:
        logging.error(f"获取模型列表失败: {e}")
        return jsonify({"success": False, "error": str(e), "models": []})


def process_zip_archive(zip_path, target_languages, translation_engine, ai_model, output_dir, base_name, timestamp, unique_id, socket_sid=None):
    """
    处理 ZIP 压缩包：解压、翻译所有文件、保持目录结构打包
    返回: (zip_name, zip_path, errors) —— errors 为部分失败任务的消息列表（全部成功时为空）
    坏 ZIP / 空 ZIP / ZIP 炸弹 → ValueError；全部任务失败 → AllTranslationsFailed。
    """
    # 创建临时解压目录
    extract_dir = os.path.join(output_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        # 解压并获取有效文件列表
        valid_files = extract_zip_files(zip_path, extract_dir)

        if not valid_files:
            raise ValueError("ZIP 文件中没有找到有效的 .json 或 .js 文件")

        total_files = len(valid_files)
        total_languages = len(target_languages)
        total_tasks = total_files * total_languages

        # 存储翻译结果：{语言: [(相对路径, 输出文件路径), ...]}
        translated_files = []
        errors = []  # 部分失败任务的可读消息（"<相对路径> (<语言>): <原因>"）
        completed_tasks = 0

        for lang_index, target_language in enumerate(target_languages):
            # 为每种语言创建输出子目录
            lang_output_dir = os.path.join(output_dir, target_language)
            os.makedirs(lang_output_dir, exist_ok=True)

            _emit_progress(
                {
                    "progress": (completed_tasks / total_tasks) * 100,
                    "message": f"开始翻译到 {target_language}...",
                },
                socket_sid,
            )

            for file_index, (relative_path, full_path) in enumerate(valid_files):
                try:
                    # 计算进度
                    task_start = completed_tasks / total_tasks * 100
                    task_end = (completed_tasks + 1) / total_tasks * 100

                    # 创建保持目录结构的输出路径
                    relative_dir = os.path.dirname(relative_path)
                    if relative_dir:
                        file_output_dir = os.path.join(lang_output_dir, relative_dir)
                        os.makedirs(file_output_dir, exist_ok=True)
                    else:
                        file_output_dir = lang_output_dir

                    # 进度回调（闭包捕获 task_start/task_end/target_language/relative_path/socket_sid）
                    def progress_callback(item_progress, message):
                        total_progress = task_start + (item_progress / 100) * (task_end - task_start)
                        _emit_progress(
                            {
                                "progress": total_progress,
                                "message": f"{target_language} - {os.path.basename(relative_path)}: {message}",
                            },
                            socket_sid,
                        )

                    _emit_progress(
                        {
                            "progress": task_start,
                            "message": f"翻译 {relative_path} 到 {target_language}...",
                        },
                        socket_sid,
                    )

                    # 翻译文件
                    output_file_name, output_file_path = translate_single_file(
                        full_path, target_language, translation_engine, ai_model,
                        file_output_dir, progress_callback
                    )

                    # 计算输出文件的相对路径（保持原始目录结构）
                    if relative_dir:
                        output_relative_path = os.path.join(target_language, relative_dir, output_file_name)
                    else:
                        output_relative_path = os.path.join(target_language, output_file_name)

                    translated_files.append((output_relative_path, output_file_path))

                    logger.info(f"翻译完成: {relative_path} -> {output_relative_path}")

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"翻译失败 {relative_path} ({target_language}): {error_msg}")
                    errors.append(f"{relative_path} ({target_language}): {error_msg}")
                    _emit_progress(
                        {
                            "progress": task_end,
                            "error": f"⚠️ {relative_path} ({target_language}) 翻译失败: {error_msg}",
                        },
                        socket_sid,
                    )

                completed_tasks += 1

        if not translated_files:
            # 全部任务失败 → 500（而非坏输入的 400）
            raise AllTranslationsFailed("ZIP 内所有文件翻译都失败了，请检查错误信息并重试")

        # 创建输出 ZIP（保持目录结构）
        zip_name = f"translations_{base_name}_{timestamp}_{unique_id}.zip"
        zip_path_output = os.path.join(OUTPUT_FOLDER, zip_name)

        create_zip_with_structure(translated_files, zip_path_output)
        logger.info(f"ZIP 文件创建完成: {zip_path_output}")

        return zip_name, zip_path_output, errors

    finally:
        # 清理解压目录
        if os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
            except Exception as e:
                logger.warning(f"清理解压目录失败: {e}")


@app.route("/translate", methods=["POST"])
def translate_file_route():
    """处理翻译请求。仅被前端 AJAX fetch 调用，一律返回 JSON（不再 flash+redirect）。

    契约：
      客户端错误（文件类型/未选语言/未知模型/无效引擎）→ 400 + {success:false, error}
      服务端错误（翻译全部失败/未捕获异常）           → 500 + {success:false, error}
      成功                                             → 200 + {success:true, zip_path, redirect_url}
                                                        部分语言失败额外带 errors 数组（仍算成功）
    """
    # 前端把 socket.id 放进 FormData（可能缺失/undefined）；用于把进度事件定向发给本客户端
    socket_sid = request.form.get("socket_sid") or None
    saved_file_path = None
    output_dir = None
    try:
        # ---------- 客户端输入校验（全部先做，通过后才落盘）----------
        if "file" not in request.files:
            return jsonify({"success": False, "error": "未上传文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "未选择文件"}), 400

        if not allowed_file(file.filename):
            return jsonify({"success": False, "error": "不支持的文件类型，仅支持 .json / .js / .zip"}), 400

        target_languages = request.form.getlist("languages")
        if not target_languages:
            return jsonify({"success": False, "error": "未选择目标语言"}), 400

        # 翻译引擎必须 ∈ {google, openrouter}
        translation_engine = request.form.get("translation_engine") or TRANSLATION_ENGINE
        if translation_engine not in _VALID_ENGINES:
            return jsonify({"success": False, "error": f"无效的翻译引擎: {translation_engine}"}), 400

        # ai_model 空串落回默认；openrouter 引擎校验 slug 合法性
        ai_model = request.form.get("ai_model") or config.DEFAULT_MODEL
        if translation_engine == "openrouter" and get_model_info(ai_model) is None:
            return jsonify({"success": False, "error": f"未知的 AI 模型: {ai_model}"}), 400

        # ---------- 落盘 ----------
        original_filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        base_name = os.path.splitext(original_filename)[0]
        file_extension = os.path.splitext(original_filename)[1].lower()
        unique_filename = f"{base_name}_{timestamp}_{unique_id}{file_extension}"

        saved_file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(saved_file_path)
        logger.info(f"File saved to: {saved_file_path}")

        output_dir = os.path.join(OUTPUT_FOLDER, f"{base_name}_{timestamp}_{unique_id}")
        os.makedirs(output_dir, exist_ok=True)

        # ========== ZIP 文件处理 ==========
        if is_zip_file(original_filename):
            try:
                zip_name, _zip_path, errors = process_zip_archive(
                    saved_file_path, target_languages, translation_engine,
                    ai_model, output_dir, base_name, timestamp, unique_id, socket_sid
                )
            except AllTranslationsFailed as e:
                # 全部任务失败 → 服务端错误 500
                _safe_remove(saved_file_path)
                _safe_rmtree(output_dir)
                return jsonify({"success": False, "error": str(e)}), 500
            except ValueError as e:
                # 坏 ZIP / 空 ZIP / ZIP 炸弹 → 客户端输入错误 400
                _safe_remove(saved_file_path)
                _safe_rmtree(output_dir)
                return jsonify({"success": False, "error": f"ZIP 处理失败: {e}"}), 400

            # 清理临时文件
            _safe_remove(saved_file_path)
            _safe_rmtree(output_dir)

            redirect_url = f"/success?zip_path=/output/{zip_name}"
            _emit_progress(
                {
                    "progress": 100,
                    "message": "ZIP 压缩包翻译全部完成！",
                    "complete": True,
                    "redirect_url": redirect_url,
                },
                socket_sid,
            )
            sleep(0.5)

            resp = {"success": True, "zip_path": f"/output/{zip_name}", "redirect_url": redirect_url}
            if errors:
                resp["errors"] = errors
            return jsonify(resp), 200

        # ========== 单文件处理 ==========
        output_files = []
        errors = []  # 部分失败语言的可读消息（"<语言>: <原因>"）
        total_languages = len(target_languages)

        for index, target_language in enumerate(target_languages):
            try:
                # 计算当前语言的进度范围
                language_start_progress = (index / total_languages) * 100
                language_end_progress = ((index + 1) / total_languages) * 100

                _emit_progress(
                    {
                        "progress": language_start_progress,
                        "message": f"开始翻译到 {target_language}...",
                    },
                    socket_sid,
                )

                # 进度回调（闭包捕获 language_start/end_progress、target_language、socket_sid）
                def progress_callback(item_progress, message):
                    total_progress = language_start_progress + (item_progress / 100) * (
                        language_end_progress - language_start_progress
                    )
                    _emit_progress(
                        {
                            "progress": total_progress,
                            "message": f"{target_language}: {message}",
                        },
                        socket_sid,
                    )

                output_file_name, output_file_path = translate_single_file(
                    saved_file_path, target_language, translation_engine,
                    ai_model, output_dir, progress_callback
                )
                output_files.append(output_file_path)
                logger.info(f"Translation to {target_language} completed: {output_file_name}")

                _emit_progress(
                    {
                        "progress": language_end_progress,
                        "message": f"{target_language} 翻译完成！",
                    },
                    socket_sid,
                )

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Translation failed for {target_language}: {error_msg}")
                errors.append(f"{target_language}: {error_msg}")

                _emit_progress(
                    {
                        "progress": (index + 1) / total_languages * 100,
                        "error": f"⚠️ {target_language} 翻译失败: {error_msg}，继续处理其他语言...",
                    },
                    socket_sid,
                )

                # 记录错误但继续处理其他语言（不要中断整个流程）
                if "速率限制" in error_msg or "Rate Limit" in error_msg:
                    logger.warning(f"{target_language}: API速率限制，跳过此语言继续处理")
                elif "配额" in error_msg or "quota" in error_msg:
                    logger.warning(f"{target_language}: API配额问题，跳过此语言继续处理")
                continue

        # 全部语言翻译都失败 → 服务端错误 500（不得让前端误判成功）
        if not output_files:
            _safe_remove(saved_file_path)
            _safe_rmtree(output_dir)
            return jsonify({"success": False, "error": "所有语言翻译都失败了，请检查错误信息并重试"}), 500

        zip_name = f"translations_{base_name}_{timestamp}_{unique_id}.zip"
        zip_path_temp = os.path.join(output_dir, zip_name)
        create_zip(output_files, zip_path_temp)

        successful_count = len(output_files)
        if successful_count < total_languages:
            logger.info(f"翻译完成：{successful_count} 个成功，{total_languages - successful_count} 个失败")

        # Move ZIP to main output folder
        zip_path = os.path.join(OUTPUT_FOLDER, zip_name)
        shutil.move(zip_path_temp, zip_path)

        # 清理临时文件
        _safe_rmtree(output_dir)
        _safe_remove(saved_file_path)

        redirect_url = f"/success?zip_path=/output/{zip_name}"
        _emit_progress(
            {
                "progress": 100,
                "message": "翻译全部完成！",
                "complete": True,
                "redirect_url": redirect_url,
            },
            socket_sid,
        )
        sleep(0.5)

        resp = {"success": True, "zip_path": f"/output/{zip_name}", "redirect_url": redirect_url}
        if errors:
            resp["errors"] = errors
        return jsonify(resp), 200

    except Exception as e:
        # 未捕获异常 → 服务端错误 500
        logger.error(f"翻译过程发生未捕获异常: {e}")
        _safe_remove(saved_file_path)
        _safe_rmtree(output_dir)
        return jsonify({"success": False, "error": f"翻译过程发生错误: {e}"}), 500


@app.route("/api/estimate-cost", methods=["POST"])
def estimate_cost_route():
    """估算翻译成本（字符数估算，仅 OpenRouter 引擎）"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "未上传文件"}), 400

        file = request.files["file"]
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "无效的文件类型"}), 400

        target_languages = request.form.getlist("languages")
        translation_engine = request.form.get("translation_engine", "openrouter")
        ai_model = request.form.get("ai_model", config.DEFAULT_MODEL)

        if not target_languages:
            return jsonify({"error": "未选择目标语言"}), 400

        # Google Translate: 费用由 Google Cloud 账户管理，不做应用层估算
        if translation_engine != "openrouter":
            return jsonify({
                "engine": "google",
                "message": "Google Translate API 费用由您的 Google Cloud 账户管理",
                "estimated_cost": "请查看 Google Cloud Console"
            })

        # 保存临时文件并估算 —— try/finally 保证 estimate_cost 抛异常时也清理临时文件（F: 修泄漏）
        import tempfile
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp_path = tmp_file.name
        tmp_file.close()
        try:
            file.save(tmp_path)
            token_info = estimate_cost(tmp_path, target_languages, ai_model)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if "error" in token_info:
            return jsonify({"success": False, "error": token_info["error"]}), 500

        return jsonify({
            "success": True,
            "engine": "openrouter",
            "model": token_info.get("model_name", "Unknown"),
            "estimation": token_info,
            "formatted_summary": format_cost_summary(token_info)
        })

    except Exception as e:
        logger.error(f"费用预估失败: {e}")
        return jsonify({"error": str(e)}), 500


@socketio.on("connect", namespace="/test")
def test_connect():
    print("Client connected")


@socketio.on("disconnect", namespace="/test")
def test_disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    import errno
    import sys

    # 默认端口避开 macOS AirPlay Receiver（占 *:5000 / *:7000）
    PORT = 5050

    print("=" * 50)
    print("🚀 翻译应用启动中...")
    print(f"📊 默认翻译引擎: {TRANSLATION_ENGINE}")
    if TRANSLATION_ENGINE == "openrouter" or config.OPENROUTER_API_KEY:
        print(f"🤖 默认 AI 模型: {config.DEFAULT_MODEL}")
        print(f"🔑 OpenRouter API Key: {'✅ 已配置' if config.OPENROUTER_API_KEY else '❌ 未配置'}")
    print(f"🔌 监听地址: http://127.0.0.1:{PORT}")
    print("=" * 50)

    try:
        app.run(debug=True, host="127.0.0.1", port=PORT)
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        print()
        print(f"❌ 端口 {PORT} 已被占用，无法启动。")
        print()
        print("排查步骤：")
        print(f"  1. 查占用者：lsof -nP -iTCP:{PORT} -sTCP:LISTEN")
        print(f"  2. 若是遗留 Python（debug reloader 孤儿常见）：")
        print(f"     lsof -nP -iTCP:{PORT} -sTCP:LISTEN -t | xargs kill")
        print(f"  3. 2 秒后再跑 ./start.sh")
        print()
        sys.exit(1)
