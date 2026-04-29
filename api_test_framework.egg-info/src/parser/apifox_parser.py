"""
Apifox 导出格式解析器
适配 Apifox 自定义字段结构
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.types import ApiInfo
from src.parser.normalizer import build_api_info
from src.utils.logger import logger


def parse_apifox(file_path: str | Path) -> list[ApiInfo]:
    """
    解析 Apifox 导出的 JSON 文件

    Apifox 导出格式大致结构：
    {
      "apiDefinition": { ... },        # 可能包含 OpenAPI 子集
      "apiFolders": [ ... ],           # 接口分组
      "apiDetailList": [               # 接口详情列表
        {
          "id": "xxx",
          "name": "接口名称",
          "method": "GET",
          "path": "/api/users",
          "description": "...",
          "tags": ["用户管理"],
          "request": { ... },
          "response": [ ... ],
          ...
        }
      ]
    }
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文档文件不存在: {path}")

    content = path.read_text(encoding="utf-8")
    doc = json.loads(content)

    if not doc:
        raise ValueError("文档内容为空")

    logger.info(f"解析 Apifox 文档: {path.name}")

    # 情况 1：标准 Apifox 导出格式
    if "apiDetailList" in doc:
        return _parse_apifox_detail_list(doc, path.name)

    # 情况 2：可能是 OpenAPI 兼容格式（Apifox 也支持导出 OpenAPI）
    if "paths" in doc:
        from src.parser.openapi_parser import parse_openapi
        return parse_openapi(path)

    raise ValueError("无法识别的 Apifox 文档格式（缺少 apiDetailList 或 paths）")


def _parse_apifox_detail_list(doc: dict[str, Any], source: str) -> list[ApiInfo]:
    """解析 Apifox apiDetailList"""
    apis: list[ApiInfo] = []
    detail_list = doc.get("apiDetailList", [])

    # 构建文件夹名称映射
    folder_map = {}
    for folder in doc.get("apiFolders", []):
        folder_map[str(folder.get("id", ""))] = folder.get("name", "默认")

    for item in detail_list:
        api = _parse_apifox_api(item, folder_map, source)
        if api:
            apis.append(api)

    logger.info(f"从 Apifox 文档中提取了 {len(apis)} 个接口")
    return apis


def _parse_apifox_api(
    item: dict[str, Any],
    folder_map: dict[str, str],
    source: str,
) -> ApiInfo | None:
    """解析单个 Apifox 接口"""
    method = item.get("method", "GET")
    path = item.get("path", "")

    if not path:
        return None

    name = item.get("name", f"{method} {path}")
    description = item.get("description", "")
    tags = item.get("tags", [])

    # 确定所属分组
    folder_id = str(item.get("folderId", ""))
    section = folder_map.get(folder_id, tags[0] if tags else "默认")

    # 提取请求参数
    request = item.get("request", {})
    path_params = []
    query_params = []
    header_params = []

    for param in request.get("params", []):
        param_dict = {
            "name": param.get("name", ""),
            "type": param.get("type", "string"),
            "required": param.get("required", False),
            "description": param.get("description", ""),
            "example": param.get("example"),
        }

        param_in = param.get("in", param.get("paramIn", "query"))
        if param_in == "path":
            param_dict["in"] = "path"
            path_params.append(param_dict)
        elif param_in == "header":
            param_dict["in"] = "header"
            header_params.append(param_dict)
        else:
            param_dict["in"] = "query"
            query_params.append(param_dict)

    # 请求体
    request_body = _convert_apifox_body(request.get("body", {}))

    # 响应
    response_schemas: dict[str, Any] = {}
    responses = item.get("response", [])
    if isinstance(responses, list):
        for resp in responses:
            status_code = str(resp.get("statusCode", 200))
            resp_body = resp.get("body", {})
            if resp_body:
                response_schemas[status_code] = _convert_apifox_response_body(resp_body)

    # 认证
    auth_required = bool(item.get("auth", {}).get("type")) or bool(
        request.get("auth", {}).get("type")
    )

    # 示例
    examples: dict[str, Any] = {}
    if request_body and request_body.get("example"):
        examples["request_example"] = request_body["example"]
    for status, schema in response_schemas.items():
        if schema.get("example"):
            examples["response_example"] = schema["example"]
            break

    return build_api_info(
        name=name,
        method=method,
        path=path,
        summary=description,
        description=description,
        path_params=path_params,
        query_params=query_params,
        header_params=header_params,
        request_body=request_body,
        response_schemas=response_schemas,
        auth_required=auth_required,
        tags=tags,
        examples=examples,
        source=source,
        section=section,
    )


def _convert_apifox_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """将 Apifox 请求体转换为 OpenAPI 兼容格式"""
    if not body:
        return None

    content_type = body.get("type", "application/json")

    # JSON 格式
    if content_type in ("application/json", "none", None):
        raw_body = body.get("raw", body.get("jsonBody", body.get("formDataBody", {})))
        if raw_body:
            return {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": raw_body if isinstance(raw_body, dict) else {},
                        },
                        "example": raw_body,
                    }
                }
            }

    # Form-data / x-www-form-urlencoded
    form_data = body.get("formDataBody", body.get("formData", []))
    if form_data and isinstance(form_data, list) and len(form_data) > 0:
        props = {}
        required = []
        for field in form_data:
            field_name = field.get("name", "")
            if field_name:
                props[field_name] = {"type": "string", "description": field.get("description", "")}
                if field.get("required"):
                    required.append(field_name)
        return {
            "content": {
                "multipart/form-data": {
                    "schema": {"type": "object", "properties": props, "required": required}
                }
            }
        }

    return None


def _convert_apifox_response_body(body: dict[str, Any]) -> dict[str, Any]:
    """将 Apifox 响应体转换为 OpenAPI 兼容格式"""
    raw_body = body.get("raw", body.get("jsonBody", body.get("formDataBody", {})))
    if raw_body:
        return {
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": raw_body if isinstance(raw_body, dict) else {}},
                    "example": raw_body,
                }
            }
        }
    return {"content": {}}
