"""单文件翻译分发 —— 按 引擎 × 扩展名 选具体翻译器。

无 Flask / Socket.IO 耦合，故 app.py（Web）与 cli.py（无头）共用同一份分发，
避免分发逻辑出现多副本（SoT）。具体翻译器（Google 递归 / LLM 批处理）结构不同，
不在此强行抽象，仅做分发。
"""
import os

from translate import translate_file
from translate_llm import translate_json_file_llm, translate_js_file_llm


def translate_single_file(
    file_path, target_language, translation_engine, ai_model, output_dir,
    progress_callback=None,
):
    """翻译单个文件，返回 (输出文件名, 输出文件完整路径)。

    Args:
        file_path: 源 .json/.js 文件路径
        target_language: 目标语言代码
        translation_engine: 'openrouter'（LLM）或 'google'
        ai_model: OpenRouter 模型 slug（google 引擎忽略）
        output_dir: 输出目录
        progress_callback: 进度回调 (pct: float, message: str)
    """
    file_extension = os.path.splitext(file_path)[1].lower()

    if translation_engine == "openrouter":
        if file_extension == ".json":
            output_file_name = translate_json_file_llm(
                file_path, target_language, progress_callback, ai_model, output_dir
            )
        elif file_extension == ".js":
            output_file_name = translate_js_file_llm(
                file_path, target_language, progress_callback, ai_model, output_dir
            )
        else:
            raise ValueError(f"不支持的文件类型: {file_extension}")
    else:
        output_file_name = translate_file(
            file_path, target_language, progress_callback, output_dir
        )

    return output_file_name, os.path.join(output_dir, output_file_name)
