# translate.py
import os
import json
import zipfile
import re
from google.cloud import translate_v2 as translate

# Initialize the client
os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"
] = "./universal-team-395508-399550064d46.json"
translate_client = translate.Client()


def translate_text(text, target_language="en"):
    """Translates a text to the target language using Google Cloud Translation."""
    # Replace special quotation marks and colon with placeholders
    text = (
        text.replace("“", "<START_QUOTE>")
        .replace("”", "<END_QUOTE>")
        .replace(":", "<COLON>")
        .replace("'", "<SINGLE_QUOTE>")
        .replace('"', "<DOUBLE_QUOTE>")
    )

    try:
        translation = translate_client.translate(text, target_language=target_language)
        translation_text = translation.get("translatedText", "")

        # Post-process to replace HTML encoded characters, placeholders with actual characters and fix the colon
        translation_text = (
            translation_text.replace("&#39;", "'")
            .replace("&quot;", '"')
            .replace("&amp;", "&")
            .replace("<START_QUOTE>", "“")
            .replace("<END_QUOTE>", "”")
            .replace("<COLON>", ":")
            .replace("<SINGLE_QUOTE>", "'")
            .replace("<DOUBLE_QUOTE>", '"')
        )

        # Capitalize the first letter if the string is not empty
        if translation_text:
            translation_text = translation_text[0].upper() + translation_text[1:]
        else:
            print(f"Warning: Received empty translation for text: {text}")

        # Return the processed translation text
        return translation_text

    except Exception as e:
        error_message = f"An error occurred during translation: {e}"
        print(error_message)
        # Depending on your error handling strategy, you might want to re-raise the error or return None
        raise  # This will re-raise the last exception


def translate_locale_file(source_file_path, target_language="en"):
    """Reads a locale JS file, translates the strings, and writes the translated content to a new file."""
    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Updated regex to match your file structure
    # The regex (\w+):\s*\'(.*?)\' is tailored to match keys without quotes and values within quotes
    key_value_pairs = re.findall(r"(\w+):\s*\'(.*?)\'", content, re.DOTALL)

    print(key_value_pairs)  # Debug: Check if the pairs are being captured

    translated_key_value_pairs = []

    for key, value in key_value_pairs:
        translated_value = translate_text(value.strip(), target_language)
        translated_key_value_pairs.append((key, translated_value))

    # Construct the translated content
    translated_content = ["const lang = {\n"]
    for key, value in translated_key_value_pairs:
        translated_content.append(f'  {key}: "{value}",\n')
    translated_content.append("};\n\nexport default lang;")

    output_file_name = f"{target_language}.js"

    # Write to a new file
    output_path = os.path.join("output", output_file_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(translated_content))

    return output_file_name


def translate_json_file(source_file_path, target_language="en"):
    """Reads a JSON file, translates the strings, and writes the translated content to a new file."""
    with open(source_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    translated_data = {}
    for key, value in data.items():
        translated_value = translate_text(value.strip(), target_language)
        translated_data[key] = translated_value

    output_file_name = f"{target_language}.json"
    output_path = os.path.join("output", output_file_name)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    return output_file_name


def create_zip(files, output_filename):
    """Create a ZIP archive from the given list of files."""
    with zipfile.ZipFile(output_filename, "w") as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))


def translate_file(source_file_path, target_language="en"):
    """Determines the file type and calls the appropriate translation function."""
    file_extension = source_file_path.split(".")[-1]
    if file_extension == "json":
        return translate_json_file(source_file_path, target_language)
    elif file_extension == "js":
        return translate_locale_file(source_file_path, target_language)
    else:
        raise ValueError("Unsupported file type")
