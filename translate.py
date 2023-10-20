import os
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

    translation = translate_client.translate(text, target_language=target_language)

    # Post-process to replace HTML encoded characters, placeholders with actual characters and fix the colon
    translation = (
        translation["translatedText"]
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )
    translation = (
        translation.replace("<START_QUOTE>", "“")
        .replace("<END_QUOTE>", "”")
        .replace("<COLON>", ":")
        .replace("<SINGLE_QUOTE>", "'")
        .replace("<DOUBLE_QUOTE>", '"')
    )

    # Capitalize the first letter
    translation = translation[0].upper() + translation[1:]

    return translation


def translate_locale_file(source_file_path, target_language="en"):
    """Reads a locale JS file, translates the strings, and writes the translated content to a new file."""

    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    key_value_pairs = re.findall(
        r"(['\"]?[^\s:]+['\"]?):\s*['\"](.*?)['\"]", content, re.DOTALL
    )

    translated_key_value_pairs = []

    for key, value in key_value_pairs:
        translated_value = translate_text(value.strip(), target_language)
        translated_key_value_pairs.append((key, translated_value))

    # Construct the translated content with the export default structure
    translated_content = ["export default {\n"]
    for key, value in translated_key_value_pairs:
        formatted_value = value.strip('"')
        translated_content.append('  {}: "{}",\n'.format(key, formatted_value))
    translated_content.append("};\n")

    output_extension = source_file_path.split(".")[-1]
    output_file_name = f"{target_language}.{output_extension}"

    # Write to a new file based on the target language
    output_path = os.path.join("output", output_file_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(translated_content))

    return output_file_name


def create_zip(files, output_filename):
    """Create a ZIP archive from the given list of files."""

    with zipfile.ZipFile(output_filename, "w") as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))
