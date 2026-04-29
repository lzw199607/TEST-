"""
OpenAPI / Swagger 3.0 文档解析器
遍历 paths + operations，提取结构化接口信息
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.types import ApiInfo
from src.parser.normalizer import build_api_info
from src.utils.logger import logger


def parse_openapi(file_path: str | Path) -> list[ApiInfo]:
    """
    解析 OpenAPI 3.0 / Swagger JSON 或 YAML 文件

    Args:
        file_path: 文档文件路径

    Returns:
        结构化接口列表
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文档文件不存在: {path}")

    # 读取文件
    content = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        import yaml
        doc = yaml.safe_load(content)
    else:
        doc = json.loads(content)

    if not doc:
        raise ValueError("文档内容为空")

    # 识别 OpenAPI 版本
    openapi_version = doc.get("openapi", doc.get("swagger", ""))
    logger.info(f"解析 OpenAPI 文档: {path.name} (版本: {openapi_version})")

    return _parse_paths(doc, path.name)


def _parse_paths(doc: dict[str, Any], source: str) -> list[ApiInfo]:
    """遍历 paths 提取接口信息"""
    apis: list[ApiInfo] = []
    paths = doc.get("paths", {})

    # 提取全局安全声明
    global_security = doc.get("security", [])
    security_schemes = _extract_security_schemes(doc)

    # 提取全局标签描述
    tags_info = {}
    for tag_obj in doc.get("tags", []):
        tags_info[tag_obj.get("name", "")] = tag_obj.get("description", "")

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            operation = path_item.get(method)
            if not operation or not isinstance(operation, dict):
                continue

            api = _parse_operation(
                path_str=path_str,
                method=method,
                operation=operation,
                path_item=path_item,
                global_security=global_security,
                security_schemes=security_schemes,
                tags_info=tags_info,
                source=source,
            )

            if api:
                apis.append(api)

    logger.info(f"从 OpenAPI 文档中提取了 {len(apis)} 个接口")
    return apis


def _parse_operation(
    path_str: str,
    method: str,
    operation: dict[str, Any],
    path_item: dict[str, Any],
    global_security: list[dict],
    security_schemes: dict[str, dict],
    tags_info: dict[str, str],
    source: str,
) -> ApiInfo | None:
    """解析单个操作"""
    operation_id = operation.get("operationId", "")
    summary = operation.get("summary", "")
    description = operation.get("description", "")

    # 接口名称：优先使用 operationId 或 summary
    name = operation_id or summary or f"{method.upper()} {path_str}"

    # 标签 / 分组
    tags = operation.get("tags", [])
    section = tags[0] if tags else "默认"

    # 判断是否需要认证
    auth_required = _check_auth(operation, path_item, global_security, security_schemes)

    # 路径参数（可以从 path item 继承）
    path_params = _extract_params(
        path_item.get("parameters", []) + operation.get("parameters", []),
        "path",
    )

    # 查询参数
    query_params = _extract_params(operation.get("parameters", []), "query")

    # Header 参数
    header_params = _extract_params(operation.get("parameters", []), "header")

    # 请求体
    request_body = operation.get("requestBody")

    # 响应
    responses = operation.get("responses", {})

    # 提取示例
    examples: dict[str, Any] = {}
    # 请求示例
    if request_body:
        content = request_body.get("content", {})
        for ct, media in content.items():
            example = media.get("example")
            if example:
                examples["request_example"] = example
                break
    # 响应示例
    for status, resp_obj in responses.items():
        if isinstance(resp_obj, dict):
            content = resp_obj.get("content", {})
            for ct, media in content.items():
                example = media.get("example")
                if example:
                    examples["response_example"] = example
                    break
            if "response_example" in examples:
                break

    return build_api_info(
        name=name,
        method=method,
        path=path_str,
        summary=summary,
        description=description,
        path_params=path_params,
        query_params=query_params,
        header_params=header_params,
        request_body=request_body,
        response_schemas=responses,
        auth_required=auth_required,
        tags=tags,
        examples=examples,
        source=source,
        section=section,
    )


def _extract_params(params: list[dict], in_location: str) -> list[dict]:
    """按位置提取参数"""
    return [p for p in params if isinstance(p, dict) and p.get("in") == in_location]


def _check_auth(
    operation: dict,
    path_item: dict,
    global_security: list[dict],
    security_schemes: dict[str, dict],
) -> bool:
    """检查接口是否需要认证"""
    # 操作级 security 声明
    op_security = operation.get("security")
    if op_security is not None:
        # 空数组 = 不需要认证
        return len(op_security) > 0

    # path 级 security 声明
    path_security = path_item.get("security")
    if path_security is not None:
        return len(path_security) > 0

    # 全局 security 声明
    return len(global_security) > 0


def _extract_security_schemes(doc: dict) -> dict[str, dict]:
    """提取安全方案定义"""
    components = doc.get("components", {})
    return components.get("securitySchemes", {})
