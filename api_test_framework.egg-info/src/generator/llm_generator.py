"""
LLM 驱动的测试用例生成器
从结构化接口信息生成 pytest 测试代码
"""

from __future__ import annotations

import re
from pathlib import Path

from src.core.llm_client import LlmClient, LlmError
from src.core.types import ApiInfo, ChatMessage, ChatOptions
from src.parser.normalizer import group_apis_by_tag
from src.prompts.generation_prompts import (
    GENERATION_SYSTEM_PROMPT,
    build_batch_generation_prompt,
    build_generation_prompt,
)
from src.utils.logger import logger


def generate_single(
    api_info: ApiInfo,
    llm_client: LlmClient,
    context: dict | None = None,
) -> str:
    """
    为单个接口生成 pytest 测试代码

    Args:
        api_info: 结构化接口信息
        llm_client: LLM 客户端
        context: 上下文信息

    Returns:
        生成的 pytest 代码字符串
    """
    logger.info(f"AI 生成测试用例: {api_info.name}")

    messages = [
        ChatMessage(role="system", content=GENERATION_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_generation_prompt(api_info, context)),
    ]

    try:
        response = llm_client.chat(
            messages,
            options=ChatOptions(temperature=0.2, max_tokens=8000),
        )
    except LlmError as e:
        raise RuntimeError(f"AI 生成失败 ({api_info.name}): {e}") from e

    code = _extract_python_code(response.content)

    if not code or len(code) < 50:
        raise RuntimeError(f"AI 生成的代码过短或为空 ({api_info.name})")

    return code


def generate_batch(
    apis: list[ApiInfo],
    llm_client: LlmClient,
    context: dict | None = None,
) -> dict[str, str]:
    """
    批量生成测试用例，按分组输出多个文件

    Args:
        apis: 结构化接口列表
        llm_client: LLM 客户端
        context: 上下文信息

    Returns:
        {文件名: 代码内容} 映射
    """
    groups = group_apis_by_tag(apis)
    result: dict[str, str] = {}

    for group_name, group_apis in groups.items():
        file_name = f"test_{_to_snake_case(group_name)}_api.py"
        logger.info(f"AI 批量生成: {file_name} ({len(group_apis)} 个接口)")

        try:
            messages = [
                ChatMessage(role="system", content=GENERATION_SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=build_batch_generation_prompt(group_apis, group_name, context),
                ),
            ]

            response = llm_client.chat(
                messages,
                options=ChatOptions(temperature=0.2, max_tokens=16000),
            )

            code = _extract_python_code(response.content)

            if code and len(code) >= 50:
                result[file_name] = code
                logger.info(f"AI 生成成功: {file_name} ({len(code)} 字符)")
            else:
                logger.warning(f"AI 生成的代码过短: {file_name}，将使用模板生成")
                result[file_name] = _fallback_to_template(group_apis)

        except LlmError as e:
            logger.warning(f"AI 批量生成失败 ({group_name}): {e}，降级为逐个生成")
            # 降级：逐个生成
            batch_code = _generate_one_by_one(group_apis, llm_client, context)
            if batch_code:
                result[file_name] = batch_code
            else:
                logger.warning(f"逐个生成也失败，使用模板: {file_name}")
                result[file_name] = _fallback_to_template(group_apis)

    return result


def _generate_one_by_one(
    apis: list[ApiInfo],
    llm_client: LlmClient,
    context: dict | None = None,
) -> str | None:
    """逐个接口生成测试代码并合并"""
    import re

    class_name = _to_pascal_case(apis[0].section or apis[0].tags[0] if apis[0].tags else "default")
    all_methods: list[str] = []

    for api in apis:
        try:
            code = generate_single(api, llm_client, context)
            methods = _extract_test_methods(code)
            all_methods.extend(methods)
        except Exception as e:
            logger.warning(f"单个生成失败 ({api.name}): {e}")

    if not all_methods:
        return None

    header = (
        "import pytest\n"
        "from src.client import BaseClient\n"
        "from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time\n"
        "\n\n"
        f"class Test{class_name}API:\n"
        f'    """{class_name} 接口测试（AI 生成）"""\n'
        "\n"
        "    @pytest.fixture(autouse=True)\n"
        "    def setup(self, api_client):\n"
        "        self.client = api_client\n"
    )

    return header + "\n".join(all_methods)


def _extract_python_code(content: str) -> str:
    """从 LLM 响应中提取 Python 代码"""
    # 尝试从 markdown 代码块中提取
    py_match = re.search(r"```(?:python|py)\s*([\s\S]*?)```", content)
    if py_match:
        return py_match.group(1).strip()

    # 尝试从通用代码块中提取
    code_match = re.search(r"```\s*([\s\S]*?)```", content)
    if code_match:
        return code_match.group(1).strip()

    # 如果内容本身看起来像代码
    if "import pytest" in content or "def test_" in content:
        return content.strip()

    return ""


def _extract_test_methods(code: str) -> list[str]:
    """从测试代码中提取测试方法（去除 import 和 class 定义）"""
    lines = code.split("\n")
    methods: list[str] = []
    in_method = False
    method_indent = ""

    for line in lines:
        stripped = line.strip()

        # 跳过 import
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue

        # 跳过 class 定义行
        if stripped.startswith("class "):
            continue

        # 检测方法定义
        if stripped.startswith("def test_") or stripped.startswith("def setup"):
            in_method = True
            method_indent = line[:len(line) - len(line.lstrip())]
            methods.append("")
            methods.append(line)
        elif in_method:
            # 遇到同级别或更低缩进的 def，结束方法
            if stripped.startswith("def ") and not line.startswith(method_indent + " " * 4):
                in_method = False
            methods.append(line)

    return methods


def _fallback_to_template(apis: list[ApiInfo]) -> str:
    """降级到模板生成"""
    from src.generator.template_generator import generate_template_tests_batch
    batch = generate_template_tests_batch(apis)
    return next(iter(batch.values()), "")


def _to_snake_case(name: str) -> str:
    """转换为 snake_case"""
    import re
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name).strip("_")
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _to_pascal_case(name: str) -> str:
    """转换为 PascalCase"""
    return "".join(word.capitalize() for word in _to_snake_case(name).split("_") if word)
