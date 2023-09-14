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
        translation["translatedText"].replace("&#39;", "'").replace("&quot;", '"')
    )
    translation = (
        translation.replace("<START_QUOTE>", "“")
        .replace("<END_QUOTE>", "”")
        .replace("<COLON>", ":")
        .replace("<SINGLE_QUOTE>", "'")
        .replace("<DOUBLE_QUOTE>", '"')
    )

    return translation


def translate_locale_file(source_file_path, target_language="en"):
    """Reads a locale JS file, translates the strings, and returns the name of the translated file."""
    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.readlines()

    key_value_pairs = []
    in_multiline_value = False
    multiline_key = ""
    multiline_value = ""

    # Variables to detect the start and end of the lang object
    start_detected = False
    end_detected = False
    variable_name = None
    direct_export_detected = False

    for index, line in enumerate(content):
        stripped_line = line.strip()

        # Detect the start and end of the object
        if "const" in line and "=" in line and "{" in line:
            start_detected = True
            variable_name = re.search(r"const\s+(\w+)\s*=", line).group(1)
        elif "export default" in line and "{" in line:
            start_detected = True
            direct_export_detected = True
        elif "}" in line and "export default" in line:
            end_detected = True

        if not start_detected or end_detected:
            continue  # Skip lines outside the object

        # If we are inside a multi-line value, continue appending
        if in_multiline_value:
            multiline_value += " " + stripped_line
            if (
                stripped_line.endswith(",")
                or stripped_line.endswith("'")
                or stripped_line.endswith("`")
            ):
                in_multiline_value = False
                translated_value = translate_text(
                    multiline_value.rstrip(",")[1:-1], target_language
                )
                key_value_pairs.append((multiline_key, translated_value))
                multiline_key = ""
                multiline_value = ""
            continue

        # If the line contains a colon but doesn't end with a typical string delimiter, it's likely the start of a multi-line value
        if ":" in line and not (
            line.endswith(",") or line.endswith("'") or line.endswith("`")
        ):
            key, value = [item.strip() for item in line.split(":", 1)]
            multiline_key = key
            multiline_value = value
            in_multiline_value = True
            continue

        # If the line doesn't contain a colon, continue to the next line
        if ":" not in line:
            continue

        if '"' in line or "'" in line or "`" in line:
            key, value = [item.strip() for item in line.split(":", 1)]
            translated_value = translate_text(value.rstrip(",")[1:-1], target_language)
            key_value_pairs.append((key, translated_value))

    # Construct the final content with commas properly placed
    if direct_export_detected:
        translated_content = ["export default {\n"]
    else:
        translated_content = [f"const {variable_name} = {{\n"]

    for i, (key, value) in enumerate(key_value_pairs):
        if i == len(key_value_pairs) - 1:  # Last key-value pair
            translated_content.append(f'  {key}: "{value}"\n')
        else:
            translated_content.append(f'  {key}: "{value}",\n')
    translated_content.append(f"}};\n")

    if not direct_export_detected:
        translated_content.append(f"export default {variable_name};\n")

    output_extension = source_file_path.split(".")[-1]
    output_file_name = f"{target_language}.{output_extension}"

    # Translate and save to a new file in the /output directory based on the target language
    output_path = os.path.join("output", output_file_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(translated_content))

    return output_file_name


def create_zip(files, output_filename):
    """
    Create a ZIP archive from the given list of files.
    """
    with zipfile.ZipFile(output_filename, "w") as zipf:
        for file in files:
            zipf.write(
                file, os.path.basename(file)
            )  # Save with basename to avoid directory structure
