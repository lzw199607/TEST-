"""
文档解析入口 — 自动识别格式，路由到对应解析器
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from src.core.llm_client import LlmClient
from src.core.types import ApiInfo
from src.utils.logger import logger


def detect_format(file_path: str | Path) -> Literal["openapi", "apifox", "markdown", "unknown"]:
    """
    自动检测文档格式

    Args:
        file_path: 文档文件路径

    Returns:
        格式标识符
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return _detect_yaml_format(path)
    if suffix == ".json":
        return _detect_json_format(path)
    if suffix == ".md":
        return "markdown"

    return "unknown"


def _detect_yaml_format(path: Path) -> Literal["openapi", "unknown"]:
    """检测 YAML 文件是 OpenAPI 还是其他"""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}

        if "openapi" in doc or "swagger" in doc or "paths" in doc:
            return "openapi"
    except Exception:
        pass

    return "unknown"


def _detect_json_format(path: Path) -> Literal["openapi", "apifox", "unknown"]:
    """检测 JSON 文件格式"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        # OpenAPI / Swagger
        if "openapi" in doc or "swagger" in doc:
            return "openapi"
        if "paths" in doc and isinstance(doc["paths"], dict):
            return "openapi"

        # Apifox
        if "apiDetailList" in doc:
            return "apifox"
        if "apiFolders" in doc:
            return "apifox"

        # 尝试从 Apifox 特有字段判断
        for key in ("apiDefinition", "apiFolders", "apiDetailList", "apiTestCaseList"):
            if key in doc:
                return "apifox"

    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    return "unknown"


def parse_document(
    file_path: str | Path,
    format_hint: str = "auto",
    use_llm: bool = False,
    llm_client: LlmClient | None = None,
) -> list[ApiInfo]:
    """
    解析接口文档（自动识别格式）

    Args:
        file_path: 文档文件路径
        format_hint: 格式提示（auto / openapi / apifox / markdown）
        use_llm: 是否启用 AI 辅助解析
        llm_client: LLM 客户端（use_llm=True 时必需）

    Returns:
        结构化接口列表
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文档文件不存在: {path}")

    # 确定解析格式
    if format_hint == "auto":
        fmt = detect_format(path)
    else:
        fmt = format_hint

    logger.info(f"开始解析文档: {path.name} (格式: {fmt})")

    # 优先尝试结构化解析
    if fmt == "openapi":
        from src.parser.openapi_parser import parse_openapi
        return parse_openapi(path)

    if fmt == "apifox":
        from src.parser.apifox_parser import parse_apifox
        return parse_apifox(path)

    if fmt == "markdown":
        from src.parser.markdown_parser import parse_markdown
        result = parse_markdown(path)
        if result:
            return result
        logger.warning("Markdown 解析结果为空，尝试 AI 解析...")
        fmt = "unknown"

    # 非标准格式或解析失败 → 尝试 LLM
    if use_llm and llm_client:
        from src.parser.llm_parser import parse_with_llm
        return parse_with_llm(path, llm_client)

    # 如果没有 LLM，尝试作为 OpenAPI 解析（兜底）
    if fmt == "unknown" and path.suffix in (".json", ".yaml", ".yml"):
        logger.info("尝试作为 OpenAPI 格式解析...")
        try:
            from src.parser.openapi_parser import parse_openapi
            result = parse_openapi(path)
            if result:
                return result
        except Exception:
            pass

    raise ValueError(
        f"无法解析文档: {path.name}。"
        f"支持的格式: OpenAPI JSON/YAML, Apifox JSON, Markdown。"
        f"如需解析非标准格式，请使用 --llm 参数启用 AI 辅助解析。"
    )


def parse_directory(
    dir_path: str | Path,
    format_hint: str = "auto",
    use_llm: bool = False,
    llm_client: LlmClient | None = None,
) -> list[ApiInfo]:
    """
    解析目录下所有接口文档

    Args:
        dir_path: 目录路径
        format_hint: 格式提示
        use_llm: 是否启用 AI 解析
        llm_client: LLM 客户端

    Returns:
        所有文档的接口列表
    """
    dir_p = Path(dir_path)
    if not dir_p.is_dir():
        raise NotADirectoryError(f"不是目录: {dir_p}")

    supported_extensions = {".json", ".yaml", ".yml", ".md"}
    files = sorted([
        f for f in dir_p.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ])

    if not files:
        raise FileNotFoundError(f"目录中没有找到支持的文档文件: {dir_p}")

    all_apis: list[ApiInfo] = []
    for file in files:
        try:
            apis = parse_document(file, format_hint, use_llm, llm_client)
            all_apis.extend(apis)
        except Exception as e:
            logger.warning(f"跳过文件 {file.name}: {e}")

    logger.info(f"共从 {len(files)} 个文件中提取了 {len(all_apis)} 个接口")
    return all_apis
