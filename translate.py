# translate.py
import os
import json
import zipfile
import re
from google.cloud import translate_v2 as translate

# Initialize the client
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./serviceKey.json"
translate_client = translate.Client()


def translate_text(text, target_language="en"):
    """Translates text to the target language using Google Cloud Translation."""
    # Define a placeholder for newlines to handle multiline strings properly.
    newline_placeholder = "<NEWLINE>"
    text = text.replace("\n", newline_placeholder)

    # Regular expression to identify any custom color tags and their content
    color_tag_pattern = re.compile(
        r"(\[color-[^\]]+\])(.*?)(\[/color-[^\]]+\])", re.DOTALL
    )
    segments = []
    last_end = 0
    translated_text = ""

    # Iterate over all matches
    for match in color_tag_pattern.finditer(text):
        start, end = match.span()
        # Text before the tag starts
        pre_tag_text = text[last_end:start]
        if pre_tag_text:
            pre_translation = translate_client.translate(
                pre_tag_text, target_language=target_language
            )
            translated_text += pre_translation["translatedText"]

        # The tag and content
        opening_tag, inner_content, closing_tag = (
            match.group(1),
            match.group(2),
            match.group(3),
        )
        translated_text += opening_tag  # add the opening tag as is

        # Translate the inner content if it's not empty
        if inner_content.strip():
            inner_translation = translate_client.translate(
                inner_content, target_language=target_language
            )
            translated_inner_content = inner_translation["translatedText"]
            translated_text += translated_inner_content

        translated_text += closing_tag  # add the closing tag as is

        last_end = end

    # Handle any remaining text after the last tag
    if last_end < len(text):
        remaining_text = text[last_end:]
        remaining_translation = translate_client.translate(
            remaining_text, target_language=target_language
        )
        translated_text += remaining_translation["translatedText"]

    # Restore newlines and other HTML entities
    translated_text = translated_text.replace(newline_placeholder, "\n")
    translated_text = (
        translated_text.replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )

    return translated_text


def translate_locale_file(source_file_path, target_language="en"):
    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    print("File content (first 500 characters):", content[:500])

    # Updated regex pattern to match a broader range of key characters
    key_value_pairs = re.findall(
        r'(\'[^\']+\'|[^\s:]+):\s*(`.*?`|".*?"|\'.*?\')', content, re.DOTALL
    )
    print(f"Found {len(key_value_pairs)} key-value pairs")

    translated_key_value_pairs = []

    for key, value in key_value_pairs:
        key = key.strip("'")  # Remove single quotes from key if present

        try:
            cleaned_value = value.strip().strip("`\"'")
            translated_value = translate_text(cleaned_value, target_language)
            translated_key_value_pairs.append((key, translated_value))
        except Exception as e:
            print(f"Error translating {key}: {value}. Error: {e}")

    # Construct the translated content using "export default" format
    translated_content = ["export default {\n"]
    for key, value in translated_key_value_pairs:
        translated_content.append(f'  "{key}": "{value}",\n')
    translated_content.append("};\n")

    output_file_name = f"{target_language}.js"

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
