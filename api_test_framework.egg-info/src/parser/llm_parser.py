"""
LLM 辅助文档解析器
使用 AI 从自然语言文档、非标准格式文档中提取结构化接口信息
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.llm_client import LlmClient, LlmError
from src.core.types import ApiInfo, ChatMessage, ChatOptions
from src.parser.normalizer import build_api_info
from src.prompts.extraction_prompts import build_api_extraction_prompt, API_EXTRACTION_SYSTEM_PROMPT
from src.utils.logger import logger


def parse_with_llm(
    file_path: str | Path,
    llm_client: LlmClient,
) -> list[ApiInfo]:
    """
    使用 LLM 从文档中提取结构化接口信息

    Args:
        file_path: 文档文件路径
        llm_client: LLM 客户端实例

    Returns:
        结构化接口列表
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文档文件不存在: {path}")

    content = path.read_text(encoding="utf-8")
    logger.info(f"使用 AI 解析文档: {path.name}")

    # 长文档分块处理（每块不超过 12000 字符）
    chunk_size = 12000
    if len(content) <= chunk_size:
        apis = _extract_from_chunk(content, path.name, llm_client)
    else:
        apis = []
        chunks = _split_content(content, chunk_size)
        for i, chunk in enumerate(chunks):
            logger.info(f"AI 解析分块 {i + 1}/{len(chunks)}...")
            chunk_apis = _extract_from_chunk(chunk, path.name, llm_client)
            apis.extend(chunk_apis)

    logger.info(f"AI 从文档中提取了 {len(apis)} 个接口")
    return apis


def _extract_from_chunk(
    content: str,
    source: str,
    llm_client: LlmClient,
) -> list[ApiInfo]:
    """从单个文档块中提取接口信息"""
    messages = [
        ChatMessage(role="system", content=API_EXTRACTION_SYSTEM_PROMPT),
        ChatMessage(role="user", content=build_api_extraction_prompt(content, source)),
    ]

    try:
        response = llm_client.chat(
            messages,
            options=ChatOptions(temperature=0.1, max_tokens=8000, json_mode=True),
        )
    except LlmError as e:
        logger.error(f"AI 解析失败: {e}")
        return []

    return _parse_llm_response(response.content, source)


def _parse_llm_response(content: str, source: str) -> list[ApiInfo]:
    """解析 LLM 返回的 JSON 为 ApiInfo 列表"""
    raw_data = _extract_json(content)
    if not raw_data:
        logger.error("无法从 AI 响应中提取 JSON 数据")
        return []

    apis_list = raw_data.get("apis") or raw_data.get("endpoints") or raw_data.get("data") or []
    if not isinstance(apis_list, list):
        apis_list = [raw_data]

    apis: list[ApiInfo] = []
    for item in apis_list:
        if not isinstance(item, dict):
            continue

        try:
            api = build_api_info(
                name=item.get("name", ""),
                method=item.get("method", "GET"),
                path=item.get("path", ""),
                summary=item.get("summary", item.get("description", "")),
                path_params=item.get("path_params", item.get("pathParameters", [])),
                query_params=item.get("query_params", item.get("queryParameters", [])),
                header_params=item.get("header_params", []),
                request_body=item.get("request_body", item.get("requestBody")),
                response_schemas=item.get("response_schemas", item.get("responses", {})),
                auth_required=item.get("auth_required", item.get("authRequired", False)),
                tags=item.get("tags", []),
                examples=item.get("examples", {}),
                source=source,
                section=item.get("section", item.get("tags", ["默认"])[0] if item.get("tags") else "默认"),
            )
            apis.append(api)
        except Exception as e:
            logger.warning(f"解析单个接口信息失败: {e}")

    return apis


def _extract_json(content: str) -> dict | None:
    """从 LLM 响应中提取 JSON（兼容 markdown 代码块）"""
    # 尝试直接解析
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    import re
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _split_content(content: str, chunk_size: int) -> list[str]:
    """按段落边界分割长文档"""
    if len(content) <= chunk_size:
        return [content]

    chunks: list[str] = []
    paragraphs = content.split("\n\n")
    current_chunk: list[str] = []
    current_length = 0

    for para in paragraphs:
        if current_length + len(para) > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(para)
        current_length += len(para) + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
