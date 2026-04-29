"""
接口信息标准化 — 确保所有解析器输出统一格式
"""

from __future__ import annotations

from typing import Any

from src.core.types import ApiInfo, BodySchema, HttpMethod, Param, ParamStyle, ParamType


def normalize_param(raw: dict[str, Any], style: ParamStyle = ParamStyle.QUERY) -> Param:
    """
    将原始参数字典标准化为 Param 对象

    支持 OpenAPI 3.0、Apifox、自由格式等多种来源的参数定义。
    """
    # 类型映射（兼容多种命名风格）
    type_map = {
        "string": ParamType.STRING, "str": ParamType.STRING,
        "integer": ParamType.INTEGER, "int": ParamType.INTEGER, "int32": ParamType.INTEGER, "int64": ParamType.INTEGER,
        "number": ParamType.NUMBER, "float": ParamType.NUMBER, "double": ParamType.NUMBER,
        "boolean": ParamType.BOOLEAN, "bool": ParamType.BOOLEAN,
        "array": ParamType.ARRAY,
        "object": ParamType.OBJECT,
    }

    raw_type = str(raw.get("type", "string")).lower()
    param_type = type_map.get(raw_type, ParamType.STRING)

    # Schema 内嵌的情况（OpenAPI 3.0 的 request body）
    schema = raw.get("schema") or {}
    if schema and not raw.get("type"):
        schema_type = str(schema.get("type", "string")).lower()
        param_type = type_map.get(schema_type, ParamType.STRING)

    # 提取枚举值
    enum_values = raw.get("enum") or schema.get("enum") or []
    enum_values = [str(v) for v in enum_values]

    # 提取约束
    constraints: dict[str, Any] = {}
    for constraint_key in ("minLength", "maxLength", "minimum", "maximum", "pattern", "format"):
        val = raw.get(constraint_key) or schema.get(constraint_key)
        if val is not None:
            constraints[constraint_key] = val

    return Param(
        name=str(raw.get("name", "")),
        type=param_type,
        style=style,
        required=bool(raw.get("required", False)),
        description=str(raw.get("description", "")),
        default=raw.get("default"),
        enum=enum_values,
        example=raw.get("example") or schema.get("example"),
        constraints=constraints,
    )


def normalize_body_schema(raw: dict[str, Any]) -> BodySchema | None:
    """
    将原始请求体 / 响应体定义标准化为 BodySchema

    兼容 OpenAPI 3.0 requestBody 格式和 Apifox 格式。
    """
    if not raw:
        return None

    content = raw.get("content", {})

    # OpenAPI 3.0 格式：{ content: { "application/json": { schema: ..., example: ... } } }
    if content:
        json_content = content.get("application/json") or content.get("*/*") or {}
        if not json_content and content:
            # 取第一个 content type
            json_content = next(iter(content.values()), {})

        schema = json_content.get("schema", {})
        example = json_content.get("example")

        # 提取必填字段
        required_fields = schema.get("required", [])

        return BodySchema(
            content_type=next(iter(content.keys()), "application/json"),
            schema=schema,
            example=example,
            required_fields=required_fields if isinstance(required_fields, list) else [],
        )

    # 简单格式：{ type: "object", properties: {...} }
    if raw.get("type") or raw.get("properties"):
        properties = raw.get("properties", {})
        required_fields = raw.get("required", [])

        return BodySchema(
            content_type="application/json",
            schema=raw,
            example=raw.get("example"),
            required_fields=required_fields if isinstance(required_fields, list) else [],
        )

    return None


def normalize_response_schemas(responses: dict[str, Any]) -> dict[int, BodySchema]:
    """
    将 OpenAPI responses 对象标准化为 { status_code: BodySchema } 映射
    """
    result: dict[int, BodySchema] = {}

    if not isinstance(responses, dict):
        return result

    for status_code_str, response_obj in responses.items():
        try:
            status_code = int(status_code_str)
        except (ValueError, TypeError):
            continue

        schema = normalize_body_schema(response_obj)
        if schema:
            result[status_code] = schema

    return result


def build_api_info(
    name: str,
    method: str,
    path: str,
    summary: str = "",
    path_params: list[dict] | None = None,
    query_params: list[dict] | None = None,
    header_params: list[dict] | None = None,
    request_body: dict | None = None,
    response_schemas: dict | None = None,
    auth_required: bool = False,
    tags: list[str] | None = None,
    examples: dict | None = None,
    source: str = "",
    section: str = "",
    description: str = "",
) -> ApiInfo:
    """便捷方法：从原始字典构建标准化的 ApiInfo"""
    method_enum = _parse_method(method)

    return ApiInfo(
        name=name,
        method=method_enum,
        path=path,
        summary=summary,
        description=description,
        path_params=[normalize_param(p, ParamStyle.PATH) for p in (path_params or [])],
        query_params=[normalize_param(p, ParamStyle.QUERY) for p in (query_params or [])],
        header_params=[normalize_param(p, ParamStyle.HEADER) for p in (header_params or [])],
        request_body=normalize_body_schema(request_body) if request_body else None,
        response_schemas=normalize_response_schemas(response_schemas or {}),
        auth_required=auth_required,
        tags=tags or [],
        examples=examples or {},
        source=source,
        section=section,
    )


def _parse_method(method: str) -> HttpMethod:
    """解析 HTTP 方法字符串为枚举"""
    method_upper = str(method).upper().strip()
    try:
        return HttpMethod(method_upper)
    except ValueError:
        return HttpMethod.GET


def group_apis_by_tag(apis: list[ApiInfo]) -> dict[str, list[ApiInfo]]:
    """按标签分组接口列表"""
    groups: dict[str, list[ApiInfo]] = {}
    for api in apis:
        tag = api.tags[0] if api.tags else "默认"
        groups.setdefault(tag, []).append(api)
    return groups
