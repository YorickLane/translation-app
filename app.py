# app.py

from translate import translate_text, translate_file, create_zip
from translate_claude import translate_json_file_claude
from claude_models import get_claude_models
from claude_token_counter import count_tokens_for_translation, count_tokens_with_api, format_cost_summary
from flask import Flask, request, render_template, send_from_directory, flash, redirect, jsonify
import logging
from werkzeug.utils import secure_filename
import os
import uuid
import shutil
from functools import lru_cache
from google.cloud import translate_v2 as translate
import datetime
from flask_socketio import SocketIO, emit
from time import sleep
from config import SECRET_KEY, TRANSLATION_ENGINE
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
ALLOWED_EXTENSIONS = {"json", "js"}
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
        file_extension = os.path.splitext(original_filename)[1]
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

                if translation_engine == "claude":
                    # Use Claude API for translation with selected model
                    output_file_name = translate_json_file_claude(
                        saved_file_path, target_language, progress_callback, claude_model, output_dir
                    )
                else:
                    # Use Google Translate API
                    output_file_name = translate_file(
                        saved_file_path, target_language, progress_callback, output_dir
                    )
                output_files.append(os.path.join(output_dir, output_file_name))
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

                # 发送错误信息
                socketio.emit(
                    "progress",
                    {
                        "progress": (index + 1) / total_languages * 100,
                        "error": f"{target_language} 翻译失败: {error_msg}",
                    },
                    namespace="/test",
                )

                # 如果是速率限制错误，建议用户稍后重试
                if "速率限制" in error_msg or "Rate Limit" in error_msg:
                    flash(
                        f"翻译失败：API速率限制。请等待几分钟后重试，或考虑减少同时翻译的语言数量。"
                    )
                    return redirect("/")
                elif "配额" in error_msg or "quota" in error_msg:
                    flash(
                        f"翻译失败：API配额已用完。请检查Google Cloud配额设置或稍后重试。"
                    )
                    return redirect("/")
                else:
                    flash(f"翻译到 {target_language} 时发生错误: {error_msg}")
                    return redirect("/")

        # Create a ZIP archive from translated files
        zip_name = f"translations_{base_name}_{timestamp}_{unique_id}.zip"
        zip_path_temp = os.path.join(output_dir, zip_name)
        create_zip(output_files, zip_path_temp)
        print(f"ZIP file created at: {zip_path_temp}")

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
