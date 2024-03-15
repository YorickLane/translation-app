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

app = Flask(__name__)
app.secret_key = SECRET_KEY
logging.basicConfig(level=logging.DEBUG)
socketio = SocketIO(app)

# Configuration
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ALLOWED_EXTENSIONS = {"json", "js"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "./serviceKey.json"

# Google Translate Client
translate_client = translate.Client()

# Cache setup
LAST_CACHED = datetime.datetime.now()


@lru_cache(maxsize=None)
def get_supported_languages():
    global LAST_CACHED
    now = datetime.datetime.now()
    if (now - LAST_CACHED).days > 30:
        get_supported_languages.cache_clear()  # clear cache
        LAST_CACHED = now  # update the timestamp
    languages = translate_client.get_languages()
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
            print(f"Starting translation for {target_language}...")
            output_file_name = translate_file(saved_file_path, target_language)
            output_files.append(os.path.join(OUTPUT_FOLDER, output_file_name))
            print(
                f"Translation to {target_language} completed. Output file: {output_file_name}"
            )

            # Emitting progress
            progress = (index + 1) / total_languages * 100
            socketio.emit("progress", {"progress": progress}, namespace="/test")
            sleep(1)  # Simulating some delay for demonstration purposes

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
