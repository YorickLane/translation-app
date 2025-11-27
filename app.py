# app.py

from translate import translate_text, translate_file, create_zip, create_zip_with_structure
from translate_claude import translate_json_file_claude, translate_js_file_claude
from claude_models import get_claude_models
from claude_token_counter import count_tokens_for_translation, count_tokens_with_api, format_cost_summary
from flask import Flask, request, render_template, send_from_directory, flash, redirect, jsonify
import logging
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
from config import SECRET_KEY, TRANSLATION_ENGINE
import config
from google.auth.exceptions import RefreshError
import eventlet

app = Flask(__name__)
app.secret_key = SECRET_KEY
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
socketio = SocketIO(app, async_mode='threading')

# Configuration
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ALLOWED_EXTENSIONS = {"json", "js", "zip"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./serviceKey.json"

# Google Translate Client
translate_client = translate.Client()

# Cache setup
LAST_CACHED = datetime.datetime.now()


@lru_cache(maxsize=None)
def get_supported_languages():
    # now = datetime.datetime.now()
    print("Fetching supported languages...")

    try:
        languages = translate_client.get_languages()
    except RefreshError as e:
        logging.error("Token refresh error: %s", str(e))
        flash("There was an issue with authentication. Please try again later.")
        return []

    return [{"name": lang["name"], "code": lang["language"]} for lang in languages]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_zip_file(filename):
    """检查文件是否为 ZIP 文件"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "zip"


def extract_zip_files(zip_path, extract_dir):
    """
    解压 ZIP 文件，递归获取所有有效的 .json/.js 文件
    返回: [(相对路径, 绝对路径), ...]
    """
    valid_files = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # 安全检查：防止路径穿越攻击
            for name in zf.namelist():
                if '..' in name or name.startswith('/'):
                    logger.warning(f"跳过可疑路径: {name}")
                    continue

            # 解压所有文件
            zf.extractall(extract_dir)

            # 递归查找有效文件
            for name in zf.namelist():
                # 跳过 macOS 资源文件和目录
                if name.startswith('__MACOSX') or name.startswith('._') or name.endswith('/'):
                    continue

                # 检查是否为有效的翻译文件
                if name.endswith(('.json', '.js')):
                    full_path = os.path.join(extract_dir, name)
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        valid_files.append((name, full_path))
                        logger.info(f"发现有效文件: {name}")

        logger.info(f"ZIP 解压完成，共发现 {len(valid_files)} 个有效文件")
        return valid_files

    except zipfile.BadZipFile:
        logger.error(f"无效的 ZIP 文件: {zip_path}")
        raise ValueError("上传的文件不是有效的 ZIP 压缩包")
    except Exception as e:
        logger.error(f"解压 ZIP 文件失败: {e}")
        raise


@app.route("/", methods=["GET", "POST"])
def upload_form():
    return render_template("upload.html", languages=get_supported_languages())


@app.route("/output/<filename>")
def uploaded_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


@app.route("/success")
def success_page():
    zip_path = request.args.get("zip_path", "")
    if not zip_path:
        flash("未找到翻译结果文件")
        return redirect("/")
    return render_template("success.html", zip_path=zip_path)


@app.route("/api/claude-models")
def get_claude_models_api():
    """API 端点：获取可用的 Claude 模型列表"""
    try:
        models = get_claude_models()
        return jsonify({"success": True, "models": models})
    except Exception as e:
        logging.error(f"获取模型列表失败: {e}")
        return jsonify({"success": False, "error": str(e), "models": []})


def translate_single_file(file_path, target_language, translation_engine, claude_model, output_dir, progress_callback=None):
    """
    翻译单个文件
    返回: (输出文件名, 输出文件完整路径)
    """
    file_extension = os.path.splitext(file_path)[1].lower()

    if translation_engine == "claude":
        if file_extension == ".json":
            output_file_name = translate_json_file_claude(
                file_path, target_language, progress_callback, claude_model, output_dir
            )
        elif file_extension == ".js":
            output_file_name = translate_js_file_claude(
                file_path, target_language, progress_callback, claude_model, output_dir
            )
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")
    else:
        output_file_name = translate_file(
            file_path, target_language, progress_callback, output_dir
        )

    return output_file_name, os.path.join(output_dir, output_file_name)


def process_zip_archive(zip_path, target_languages, translation_engine, claude_model, output_dir, base_name, timestamp, unique_id):
    """
    处理 ZIP 压缩包：解压、翻译所有文件、保持目录结构打包
    返回: (zip_name, zip_path) 或 None
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
        completed_tasks = 0

        for lang_index, target_language in enumerate(target_languages):
            # 为每种语言创建输出子目录
            lang_output_dir = os.path.join(output_dir, target_language)
            os.makedirs(lang_output_dir, exist_ok=True)

            socketio.emit(
                "progress",
                {
                    "progress": (completed_tasks / total_tasks) * 100,
                    "message": f"开始翻译到 {target_language}...",
                },
                namespace="/test",
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

                    # 进度回调
                    def progress_callback(item_progress, message):
                        total_progress = task_start + (item_progress / 100) * (task_end - task_start)
                        socketio.emit(
                            "progress",
                            {
                                "progress": total_progress,
                                "message": f"{target_language} - {os.path.basename(relative_path)}: {message}",
                            },
                            namespace="/test",
                        )

                    socketio.emit(
                        "progress",
                        {
                            "progress": task_start,
                            "message": f"翻译 {relative_path} 到 {target_language}...",
                        },
                        namespace="/test",
                    )

                    # 翻译文件
                    output_file_name, output_file_path = translate_single_file(
                        full_path, target_language, translation_engine, claude_model,
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
                    socketio.emit(
                        "progress",
                        {
                            "progress": task_end,
                            "error": f"⚠️ {relative_path} ({target_language}) 翻译失败: {error_msg}",
                        },
                        namespace="/test",
                    )

                completed_tasks += 1

        if not translated_files:
            raise ValueError("所有文件翻译都失败了")

        # 创建输出 ZIP（保持目录结构）
        zip_name = f"translations_{base_name}_{timestamp}_{unique_id}.zip"
        zip_path_output = os.path.join(OUTPUT_FOLDER, zip_name)

        create_zip_with_structure(translated_files, zip_path_output)
        logger.info(f"ZIP 文件创建完成: {zip_path_output}")

        return zip_name, zip_path_output

    finally:
        # 清理解压目录
        if os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
            except Exception as e:
                logger.warning(f"清理解压目录失败: {e}")


@app.route("/translate", methods=["POST"])
def translate_file_route():
    try:
        # Check if the file part is in the request
        if "file" not in request.files:
            flash("No file part")
            return redirect("/")

        file = request.files["file"]

        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == "":
            flash("No selected file")
            return redirect("/")

        if not allowed_file(file.filename):
            flash("Invalid file type")
            return redirect("/")

        # 生成唯一的文件名，避免同名文件覆盖
        original_filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        base_name = os.path.splitext(original_filename)[0]
        file_extension = os.path.splitext(original_filename)[1].lower()
        unique_filename = f"{base_name}_{timestamp}_{unique_id}{file_extension}"

        # 保存上传文件
        saved_file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(saved_file_path)
        print(f"File saved to: {saved_file_path}")

        # 创建独立的输出目录
        output_dir = os.path.join(OUTPUT_FOLDER, f"{base_name}_{timestamp}_{unique_id}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"Output directory created: {output_dir}")

        # Get target languages
        target_languages = request.form.getlist("languages")

        if not target_languages:
            flash("No target languages selected")
            return redirect("/")

        # Get translation engine from form or use default
        translation_engine = request.form.get("translation_engine", TRANSLATION_ENGINE)

        # Get Claude model if using Claude
        claude_model = request.form.get("claude_model", config.CLAUDE_MODEL)

        # ========== ZIP 文件处理 ==========
        if is_zip_file(original_filename):
            try:
                zip_name, zip_path = process_zip_archive(
                    saved_file_path, target_languages, translation_engine,
                    claude_model, output_dir, base_name, timestamp, unique_id
                )

                # 清理
                if os.path.exists(saved_file_path):
                    os.remove(saved_file_path)
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir)

                # 发送完成信号
                socketio.emit(
                    "progress",
                    {
                        "progress": 100,
                        "message": "ZIP 压缩包翻译全部完成！",
                        "complete": True,
                        "redirect_url": f"/success?zip_path=/output/{zip_name}",
                    },
                    namespace="/test",
                )

                eventlet.sleep(0.5)
                return "", 200

            except Exception as e:
                logger.error(f"ZIP 处理失败: {e}")
                flash(f"ZIP 处理失败: {e}")
                return redirect("/")

        # ========== 单文件处理（原有逻辑） ==========
        output_files = []
        total_languages = len(target_languages)

        for index, target_language in enumerate(target_languages):
            try:
                print(f"Starting translation for {target_language}...")

                # 计算当前语言的进度范围
                language_start_progress = (index / total_languages) * 100
                language_end_progress = ((index + 1) / total_languages) * 100

                # 发送开始翻译的进度
                socketio.emit(
                    "progress",
                    {
                        "progress": language_start_progress,
                        "message": f"开始翻译到 {target_language}...",
                    },
                    namespace="/test",
                )

                # 定义进度回调函数
                def progress_callback(item_progress, message):
                    # 计算总体进度：当前语言的起始进度 + 当前语言内的进度
                    total_progress = language_start_progress + (item_progress / 100) * (
                        language_end_progress - language_start_progress
                    )
                    socketio.emit(
                        "progress",
                        {
                            "progress": total_progress,
                            "message": f"{target_language}: {message}",
                        },
                        namespace="/test",
                    )

                output_file_name, output_file_path = translate_single_file(
                    saved_file_path, target_language, translation_engine,
                    claude_model, output_dir, progress_callback
                )
                output_files.append(output_file_path)
                print(
                    f"Translation to {target_language} completed. Output file: {output_file_name}"
                )

                # 发送完成进度
                socketio.emit(
                    "progress",
                    {
                        "progress": language_end_progress,
                        "message": f"{target_language} 翻译完成！",
                    },
                    namespace="/test",
                )

            except Exception as e:
                error_msg = str(e)
                print(f"Translation failed for {target_language}: {error_msg}")
                logger.error(f"Translation failed for {target_language}: {error_msg}")

                # 发送错误信息
                socketio.emit(
                    "progress",
                    {
                        "progress": (index + 1) / total_languages * 100,
                        "error": f"⚠️ {target_language} 翻译失败: {error_msg}，继续处理其他语言...",
                    },
                    namespace="/test",
                )

                # 记录错误但继续处理其他语言（不要中断整个流程）
                # 如果是速率限制或配额错误，记录警告但继续
                if "速率限制" in error_msg or "Rate Limit" in error_msg:
                    logger.warning(f"{target_language}: API速率限制，跳过此语言继续处理")
                elif "配额" in error_msg or "quota" in error_msg:
                    logger.warning(f"{target_language}: API配额问题，跳过此语言继续处理")

                # 继续处理下一个语言，而不是中断整个流程
                continue

        # Create a ZIP archive from translated files (only if we have successful translations)
        if not output_files:
            # 所有语言翻译都失败了
            flash("所有语言翻译都失败了，请检查错误信息并重试")
            return redirect("/")

        zip_name = f"translations_{base_name}_{timestamp}_{unique_id}.zip"
        zip_path_temp = os.path.join(output_dir, zip_name)
        create_zip(output_files, zip_path_temp)
        print(f"ZIP file created at: {zip_path_temp}")

        # 如果有部分语言失败，通知用户
        successful_count = len(output_files)
        if successful_count < total_languages:
            failed_count = total_languages - successful_count
            logger.info(f"翻译完成：{successful_count} 个成功，{failed_count} 个失败")

        # Move ZIP to main output folder
        zip_path = os.path.join(OUTPUT_FOLDER, zip_name)
        shutil.move(zip_path_temp, zip_path)
        print(f"ZIP moved to: {zip_path}")

        # Remove individual files after adding to ZIP
        for output_file in output_files:
            if os.path.exists(output_file):
                os.remove(output_file)

        # Remove temporary output directory
        if os.path.exists(output_dir) and os.path.isdir(output_dir):
            try:
                shutil.rmtree(output_dir)
                print(f"Cleaned up temporary directory: {output_dir}")
            except Exception as e:
                print(f"Warning: Could not remove temporary directory: {e}")

        # Remove uploaded temporary file
        if os.path.exists(saved_file_path):
            try:
                os.remove(saved_file_path)
                print(f"Cleaned up uploaded file: {saved_file_path}")
            except Exception as e:
                print(f"Warning: Could not remove uploaded file: {e}")

        # 发送完成信号
        socketio.emit(
            "progress",
            {
                "progress": 100,
                "message": "翻译全部完成！",
                "complete": True,
                "redirect_url": f"/success?zip_path=/output/{zip_name}",
            },
            namespace="/test",
        )

        # 给客户端一点时间处理完成信号
        eventlet.sleep(0.5)

        return "", 200  # 返回空响应，让客户端处理跳转

    except Exception as e:
        print(f"An error occurred during file translation: {e}")
        flash(f"An error occurred during file translation: {e}")
        return redirect("/")


@app.route("/api/estimate-cost", methods=["POST"])
def estimate_cost():
    """估算翻译成本"""
    try:
        # 检查文件
        if "file" not in request.files:
            return jsonify({"error": "未上传文件"}), 400
        
        file = request.files["file"]
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "无效的文件类型"}), 400
        
        # 获取参数
        target_languages = request.form.getlist("languages")
        translation_engine = request.form.get("translation_engine", "google")
        claude_model = request.form.get("claude_model", config.CLAUDE_MODEL)
        
        if not target_languages:
            return jsonify({"error": "未选择目标语言"}), 400
        
        # 如果不是 Claude，返回免费信息
        if translation_engine != "claude":
            return jsonify({
                "engine": "google",
                "message": "Google Translate API 费用取决于您的 Google Cloud 账户设置",
                "estimated_cost": "请查看 Google Cloud Console 了解定价"
            })
        
        # 保存临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
            file.save(tmp_file.name)
            
            # 获取计算方式（默认使用估算）
            use_api_count = request.form.get("use_api_count", "false") == "true"
            
            if use_api_count and config.CLAUDE_API_KEY:
                # 使用 API 精确计算
                logger.info(f"使用 Claude API 计算 tokens, 模型: {claude_model}")
                logger.info(f"目标语言: {target_languages}")
                token_info = count_tokens_with_api(
                    tmp_file.name, 
                    target_languages, 
                    claude_model
                )
                if not token_info:
                    # 如果 API 计算失败，回退到估算
                    logger.warning("API 计算失败，使用估算方法")
                    token_info = count_tokens_for_translation(
                        tmp_file.name, 
                        target_languages, 
                        claude_model
                    )
            else:
                # 使用估算方法
                token_info = count_tokens_for_translation(
                    tmp_file.name, 
                    target_languages, 
                    claude_model
                )
            
            # 删除临时文件
            os.unlink(tmp_file.name)
        
        # 返回预估信息
        return jsonify({
            "success": True,
            "engine": "claude",
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
    # 显示当前配置
    print("=" * 50)
    print("🚀 翻译应用启动中...")
    print(f"📊 默认翻译引擎: {TRANSLATION_ENGINE}")
    if TRANSLATION_ENGINE == "claude" or config.CLAUDE_API_KEY:
        print(f"🤖 Claude 模型: {config.CLAUDE_MODEL}")
    print("=" * 50)
    
    app.run(debug=True, host="127.0.0.1", port=5000)
