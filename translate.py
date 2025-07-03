# translate.py
import os
import json
import zipfile
import re
import time
import logging
import html
from google.cloud import translate_v2 as translate
from google.auth.exceptions import RefreshError
from google.api_core.exceptions import (
    TooManyRequests,
    ServiceUnavailable,
    GoogleAPIError,
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the client
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./serviceKey.json"
translate_client = translate.Client()

# 配置重试和速率限制
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒，重试延迟
BATCH_SIZE = 10  # 每批处理的文本数量
REQUEST_DELAY = 0.1  # 请求间隔（秒）


def safe_translate_text(text, target_language="en", retries=0):
    """安全的翻译函数，包含重试机制和错误处理"""
    if not text or not text.strip():
        return text

    try:
        # 添加请求间隔，避免速率限制
        time.sleep(REQUEST_DELAY)

        result = translate_client.translate(text, target_language=target_language)
        # 解码 HTML 实体，修复如 &#39; 等编码问题
        return html.unescape(result["translatedText"])

    except TooManyRequests as e:
        logger.warning(f"Rate limit exceeded, attempt {retries + 1}/{MAX_RETRIES}")
        if retries < MAX_RETRIES:
            # 更长的指数退避策略
            delay = RETRY_DELAY * (3**retries)  # 使用3的指数而不是2
            logger.info(f"Rate limit hit, waiting {delay} seconds before retry...")
            time.sleep(delay)
            return safe_translate_text(text, target_language, retries + 1)
        else:
            logger.error("Max retries exceeded for rate limit")
            raise Exception(f"翻译失败：API速率限制。请检查Google Cloud计费账号状态")

    except ServiceUnavailable as e:
        logger.warning(f"Service unavailable, attempt {retries + 1}/{MAX_RETRIES}")
        if retries < MAX_RETRIES:
            delay = RETRY_DELAY * (retries + 1)
            logger.info(f"Waiting {delay} seconds before retry...")
            time.sleep(delay)
            return safe_translate_text(text, target_language, retries + 1)
        else:
            logger.error("Max retries exceeded for service unavailable")
            raise Exception(f"翻译失败：服务暂时不可用，请稍后重试")

    except RefreshError as e:
        logger.error(f"Token refresh error: {e}")
        raise Exception(f"翻译失败：认证错误，请检查Google Cloud凭证")

    except GoogleAPIError as e:
        logger.error(f"Google API error: {e}")
        if "quota" in str(e).lower() or "billing" in str(e).lower():
            raise Exception(f"翻译失败：请检查Google Cloud计费账号和配额设置")
        else:
            raise Exception(f"翻译失败：{str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error during translation: {e}")
        if retries < MAX_RETRIES:
            delay = RETRY_DELAY
            logger.info(f"Waiting {delay} seconds before retry...")
            time.sleep(delay)
            return safe_translate_text(text, target_language, retries + 1)
        else:
            raise Exception(f"翻译失败：{str(e)}")


def translate_text(text, target_language="en"):
    """翻译文本，处理特殊标签和格式"""
    if not text or not text.strip():
        return text

    # Define a placeholder for newlines to handle multiline strings properly.
    newline_placeholder = "<NEWLINE>"
    text = text.replace("\\n", newline_placeholder)

    # Regular expression to identify any custom color tags and their content
    color_tag_pattern = re.compile(
        r"(\[color-[^\]]+\])(.*?)(\[/color-[^\]]+\])", re.DOTALL
    )

    translated_text = ""
    last_end = 0

    try:
        # Iterate over all matches
        for match in color_tag_pattern.finditer(text):
            start, end = match.span()
            # Text before the tag starts
            pre_tag_text = text[last_end:start]
            if pre_tag_text.strip():
                translated_text += safe_translate_text(pre_tag_text, target_language)

            # The tag and content
            opening_tag, inner_content, closing_tag = (
                match.group(1),
                match.group(2),
                match.group(3),
            )
            translated_text += opening_tag  # add the opening tag as is

            # Translate the inner content if it's not empty
            if inner_content.strip():
                translated_inner_content = safe_translate_text(
                    inner_content, target_language
                )
                translated_text += translated_inner_content

            translated_text += closing_tag  # add the closing tag as is
            last_end = end

        # Handle any remaining text after the last tag
        if last_end < len(text):
            remaining_text = text[last_end:]
            if remaining_text.strip():
                translated_text += safe_translate_text(remaining_text, target_language)

        # 如果没有特殊标签，直接翻译整个文本
        if not color_tag_pattern.search(text):
            translated_text = safe_translate_text(text, target_language)

    except Exception as e:
        logger.error(f"Error in translate_text: {e}")
        raise

    return translated_text.replace(newline_placeholder, "\n")


def translate_json_file(source_file_path, target_language="en", progress_callback=None):
    """翻译JSON文件，支持嵌套结构和批量处理"""
    logger.info(f"开始翻译JSON文件到 {target_language}")

    with open(source_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 显示文件信息
    total_items = len(data)
    logger.info(f"文件包含 {total_items} 个项目")

    def translate_value(value):
        """递归翻译值，支持嵌套对象和数组"""
        if isinstance(value, str):
            if value.strip():  # 只翻译非空字符串
                return translate_text(value.strip(), target_language)
            return value
        elif isinstance(value, dict):
            return {k: translate_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [translate_value(item) for item in value]
        else:
            return value  # 数字、布尔值等保持不变

    try:
        translated_data = {}
        total_items = len(data)

        for i, (key, value) in enumerate(data.items(), 1):
            logger.info(f"翻译进度: {i}/{total_items} - {key}")
            translated_data[key] = translate_value(value)

            # 调用进度回调函数
            if progress_callback:
                progress = (i / total_items) * 100
                progress_callback(progress, f"正在翻译: {key} ({i}/{total_items})")

            # 每处理几个项目后稍作休息（可选）
            # 注释掉休息功能，如果需要可以取消注释
            # if i % BATCH_SIZE == 0:
            #     logger.info(f"已处理 {i} 项，休息片刻...")
            #     time.sleep(1)

        output_file_name = f"{target_language}.json"
        output_path = os.path.join("output", output_file_name)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(translated_data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON翻译完成: {output_file_name}")
        return output_file_name

    except Exception as e:
        logger.error(f"JSON文件翻译失败: {e}")
        raise


def translate_locale_file(
    source_file_path, target_language="en", progress_callback=None
):
    """翻译JavaScript语言文件"""
    logger.info(f"开始翻译JS文件到 {target_language}")

    with open(source_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    logger.info(f"文件内容预览: {content[:200]}...")

    # Updated regex pattern to match a broader range of key characters
    key_value_pairs = re.findall(
        r'(\'[^\']+\'|[^\s:]+):\s*(`.*?`|".*?"|\'.*?\')', content, re.DOTALL
    )
    logger.info(f"找到 {len(key_value_pairs)} 个键值对")

    translated_key_value_pairs = []
    total_pairs = len(key_value_pairs)

    for i, (key, value) in enumerate(key_value_pairs, 1):
        key = key.strip("'")  # Remove single quotes from key if present
        logger.info(f"翻译进度: {i}/{total_pairs} - {key}")

        try:
            cleaned_value = value.strip().strip("`\"'")
            if cleaned_value.strip():  # 只翻译非空值
                translated_value = translate_text(cleaned_value, target_language)
                translated_key_value_pairs.append((key, translated_value))
            else:
                translated_key_value_pairs.append((key, cleaned_value))

            # 调用进度回调函数
            if progress_callback:
                progress = (i / total_pairs) * 100
                progress_callback(progress, f"正在翻译: {key} ({i}/{total_pairs})")

            # 批量处理间隔（可选）
            # 注释掉休息功能，如果需要可以取消注释
            # if i % BATCH_SIZE == 0:
            #     logger.info(f"已处理 {i} 项，休息片刻...")
            #     time.sleep(1)

        except Exception as e:
            logger.error(f"翻译键值对失败 {key}: {value}. 错误: {e}")
            # 翻译失败时保留原值
            cleaned_value = value.strip().strip("`\"'")
            translated_key_value_pairs.append((key, cleaned_value))

    # Construct the translated content using "export default" format
    translated_content = ["export default {\n"]
    for key, value in translated_key_value_pairs:
        # 转义引号
        escaped_value = value.replace('"', '\\"')
        translated_content.append(f'  "{key}": "{escaped_value}",\n')
    translated_content.append("};\n")

    output_file_name = f"{target_language}.js"
    output_path = os.path.join("output", output_file_name)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(translated_content))

    logger.info(f"JS翻译完成: {output_file_name}")
    return output_file_name


def create_zip(files, output_filename):
    """Create a ZIP archive from the given list of files."""
    logger.info(f"创建ZIP文件: {output_filename}")
    try:
        with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
                    logger.info(f"添加文件到ZIP: {os.path.basename(file)}")
                else:
                    logger.warning(f"文件不存在，跳过: {file}")
        logger.info("ZIP文件创建完成")
    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        raise


def translate_file(source_file_path, target_language="en", progress_callback=None):
    """根据文件类型调用相应的翻译函数"""
    logger.info(f"开始翻译文件: {source_file_path} -> {target_language}")

    file_extension = source_file_path.split(".")[-1].lower()

    try:
        if file_extension == "json":
            return translate_json_file(
                source_file_path, target_language, progress_callback
            )
        elif file_extension == "js":
            return translate_locale_file(
                source_file_path, target_language, progress_callback
            )
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")
    except Exception as e:
        logger.error(f"文件翻译失败: {e}")
        raise
