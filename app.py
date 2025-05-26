# app.py
import eventlet

eventlet.monkey_patch(socket=True)

from translate import translate_text, translate_file, create_zip
from flask import Flask, request, render_template, send_from_directory, flash, redirect
import logging
from werkzeug.utils import secure_filename
import os
from functools import lru_cache
from google.cloud import translate_v2 as translate
import datetime
from flask_socketio import SocketIO, emit
from time import sleep
from config import SECRET_KEY
from google.auth.exceptions import RefreshError

app = Flask(__name__)
app.secret_key = SECRET_KEY
logging.basicConfig(level=logging.DEBUG)
socketio = SocketIO(app)

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

        filename = secure_filename(file.filename)
        saved_file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(saved_file_path)
        print(f"File saved to: {saved_file_path}")

        # Get target languages
        target_languages = request.form.getlist("languages")

        if not target_languages:
            flash("No target languages selected")
            return redirect("/")

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

                output_file_name = translate_file(
                    saved_file_path, target_language, progress_callback
                )
                output_files.append(os.path.join(OUTPUT_FOLDER, output_file_name))
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
        zip_name = f"translations_{filename}.zip"
        zip_path = os.path.join(OUTPUT_FOLDER, zip_name)
        create_zip(output_files, zip_path)
        print(f"ZIP file created at: {zip_path}")

        # Remove individual files after adding to ZIP
        for output_file in output_files:
            os.remove(output_file)

        return render_template("success.html", zip_path="/output/" + zip_name)

    except Exception as e:
        print(f"An error occurred during file translation: {e}")
        flash(f"An error occurred during file translation: {e}")
        return redirect("/")


@socketio.on("connect", namespace="/test")
def test_connect():
    print("Client connected")


@socketio.on("disconnect", namespace="/test")
def test_disconnect():
    print("Client disconnected")


if __name__ == "__main__":
    socketio.run(app, debug=True, host="127.0.0.1")
