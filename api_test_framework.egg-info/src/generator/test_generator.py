"""
测试用例生成入口 — AI 生成 + 模板生成的三级降级策略
降级链路：LLM 批量生成 → LLM 逐个生成 → 模板生成
"""

from __future__ import annotations

from pathlib import Path

from src.core.llm_client import LlmClient
from src.core.types import ApiInfo, FrameworkConfig
from src.generator.llm_generator import generate_batch, generate_single
from src.generator.template_generator import generate_template_test, generate_template_tests_batch
from src.parser.normalizer import group_apis_by_tag
from src.utils.logger import logger


def generate_testcases(
    apis: list[ApiInfo],
    config: FrameworkConfig,
    output_dir: str | None = None,
    llm_client: LlmClient | None = None,
) -> dict[str, str]:
    """
    生成测试用例文件

    降级策略：
    1. 如果启用 LLM 且有 API Key → LLM 批量生成
    2. LLM 批量失败 → LLM 逐个生成
    3. LLM 完全不可用 → 模板生成

    Args:
        apis: 结构化接口列表
        config: 框架配置
        output_dir: 输出目录（默认使用配置中的路径）
        llm_client: LLM 客户端（可选）

    Returns:
        {文件名: 代码内容} 映射
    """
    if not apis:
        logger.warning("没有接口信息，无法生成测试用例")
        return {}

    output = output_dir or config.generator_output_dir
    context = {
        "base_url": config.api_base_url,
    }

    # 决定生成模式
    use_llm = config.generator_use_llm and llm_client is not None

    if use_llm:
        logger.info(f"使用 AI 生成测试用例（{len(apis)} 个接口）")
        result = _generate_with_llm(apis, llm_client, context)
    else:
        logger.info(f"使用模板生成测试用例（{len(apis)} 个接口）")
        result = _generate_with_template(apis)

    # 写入文件
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}
    for file_name, code in result.items():
        file_path = output_path / file_name
        file_path.write_text(code, encoding="utf-8")
        written[file_name] = str(file_path)
        logger.info(f"生成测试文件: {file_path}")

    return written


def _generate_with_llm(
    apis: list[ApiInfo],
    llm_client: LlmClient,
    context: dict,
) -> dict[str, str]:
    """LLM 生成（已内置逐个降级，此处直接调用批量接口）"""
    try:
        return generate_batch(apis, llm_client, context)
    except Exception as e:
        logger.error(f"AI 批量生成失败: {e}，降级到模板生成")
        return _generate_with_template(apis)


def _generate_with_template(apis: list[ApiInfo]) -> dict[str, str]:
    """模板生成"""
    return generate_template_tests_batch(apis)


def generate_single_testcase(
    api: ApiInfo,
    config: FrameworkConfig,
    output_dir: str | None = None,
    llm_client: LlmClient | None = None,
) -> str | None:
    """
    为单个接口生成测试代码

    Args:
        api: 结构化接口信息
        config: 框架配置
        output_dir: 输出目录
        llm_client: LLM 客户端

    Returns:
        生成的代码或 None
    """
    use_llm = config.generator_use_llm and llm_client is not None
    context = {"base_url": config.api_base_url}

    if use_llm:
        try:
            code = generate_single(api, llm_client, context)
            return code
        except Exception as e:
            logger.warning(f"AI 单个生成失败: {e}，降级到模板")

    return generate_template_test(api)
