"""
Markdown 接口文档解析器
使用正则表达式从 Markdown 格式的接口文档中提取结构化接口信息
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.core.types import ApiInfo
from src.parser.normalizer import build_api_info
from src.utils.logger import logger


def parse_markdown(file_path: str | Path) -> list[ApiInfo]:
    """
    解析 Markdown 格式的接口文档

    支持的格式（示例）：

    ### 用户登录
    **POST** `/api/auth/login`

    请求参数：
    | 参数名 | 类型 | 必填 | 说明 |
    |--------|------|------|------|
    | username | string | 是 | 用户名 |
    | password | string | 是 | 密码 |

    请求体示例：
    ```json
    {"username": "admin", "password": "admin123"}
    ```

    响应示例：
    ```json
    {"code": 200, "data": {"token": "xxx"}}
    ```
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文档文件不存在: {path}")

    content = path.read_text(encoding="utf-8")
    logger.info(f"解析 Markdown 文档: {path.name}")

    return _parse_markdown_content(content, path.name)


def _parse_markdown_content(content: str, source: str) -> list[ApiInfo]:
    """解析 Markdown 文本内容"""
    apis: list[ApiInfo] = []

    # 按二级或三级标题分割为章节
    sections = re.split(r"\n(?=#{2,3}\s)", content)

    for section in sections:
        api = _parse_section(section, source)
        if api:
            apis.append(api)

    logger.info(f"从 Markdown 文档中提取了 {len(apis)} 个接口")
    return apis


def _parse_section(section: str, source: str) -> ApiInfo | None:
    """解析单个章节为一个接口"""
    lines = section.strip().split("\n")
    if not lines:
        return None

    # 提取标题
    title_match = re.match(r"^#{2,3}\s+(.+)", lines[0])
    if not title_match:
        return None
    title = title_match.group(1).strip()

    # 提取 HTTP 方法和路径
    method = "GET"
    api_path = ""
    section_text = "\n".join(lines[1:])

    # 格式1: **POST** `/api/xxx` 或 **POST** `/api/xxx`
    method_path_match = re.search(
        r"\*\*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\*\*\s*`?(/[^\s`\"]*)`?",
        section_text,
        re.IGNORECASE,
    )
    if method_path_match:
        method = method_path_match.group(1).upper()
        api_path = method_path_match.group(2)

    # 格式2: `POST /api/xxx` 或 `POST /api/xxx`
    if not api_path:
        method_path_match = re.search(
            r"`(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[^\s`]*)`",
            section_text,
            re.IGNORECASE,
        )
        if method_path_match:
            method = method_path_match.group(1).upper()
            api_path = method_path_match.group(2)

    if not api_path:
        return None

    # 提取描述（标题和接口声明之间的文本）
    description = _extract_description(section_text)

    # 提取参数表格
    params = _extract_param_table(section_text)
    path_params = [p for p in params if p.get("name") and p.get("name") in api_path]
    query_params = [p for p in params if p not in path_params]

    # 提取请求体 JSON 示例
    request_body = None
    request_example = _extract_code_block(section_text, ["json"], ["请求体", "请求示例", "Request"])

    if request_example:
        try:
            import json
            parsed = json.loads(request_example)
            request_body = {
                "content": {
                    "application/json": {
                        "schema": _infer_schema(parsed),
                        "example": parsed,
                    }
                }
            }
        except json.JSONDecodeError:
            pass

    # 提取响应示例
    response_example = _extract_code_block(section_text, ["json"], ["响应", "Response", "返回"])
    response_schemas: dict[str, Any] = {}
    if response_example:
        try:
            import json
            parsed = json.loads(response_example)
            # 尝试从响应中提取状态码
            status_code = parsed.get("code", parsed.get("status", 200))
            response_schemas[str(status_code)] = {
                "content": {
                    "application/json": {
                        "schema": _infer_schema(parsed),
                        "example": parsed,
                    }
                }
            }
        except json.JSONDecodeError:
            pass

    # 判断是否需要认证
    auth_required = "认证" in section_text or "Authorization" in section_text or "token" in section_text.lower()

    examples: dict[str, Any] = {}
    if request_body and request_example:
        try:
            examples["request_example"] = json.loads(request_example)
        except Exception:
            pass
    if response_example:
        try:
            examples["response_example"] = json.loads(response_example)
        except Exception:
            pass

    return build_api_info(
        name=title,
        method=method,
        path=api_path,
        summary=description,
        description=description,
        path_params=path_params,
        query_params=query_params,
        request_body=request_body,
        response_schemas=response_schemas,
        auth_required=auth_required,
        tags=[title.split("-")[0].split("_")[0].strip()],
        examples=examples,
        source=source,
        section=title,
    )


def _extract_description(text: str) -> str:
    """提取接口描述文本"""
    # 移除代码块、表格、标题
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"\|.+\|", "", text)
    text = re.sub(r"#{1,6}\s+.+", "", text)
    text = re.sub(r"\*\*(GET|POST|PUT|DELETE|PATCH)\*\*\s*`?/[^\s`\"]*`?", "", text, flags=re.IGNORECASE)

    # 取前两行有意义的文本
    lines = [line.strip() for line in text.split("\n") if line.strip() and not line.startswith("|")]
    return " ".join(lines[:2])


def _extract_param_table(text: str) -> list[dict[str, Any]]:
    """从 Markdown 表格中提取参数"""
    params: list[dict[str, Any]] = []

    # 匹配表格行
    table_rows = re.findall(r"^\|(.+)\|$", text, re.MULTILINE)
    if len(table_rows) < 2:
        return params

    # 解析表头
    headers = [cell.strip() for cell in table_rows[0].split("|")]
    if len(headers) < 2:
        return params

    # 查找关键字段索引
    name_idx = _find_header_index(headers, ["参数名", "字段名", "参数", "字段", "name", "param"])
    type_idx = _find_header_index(headers, ["类型", "type"])
    required_idx = _find_header_index(headers, ["必填", "required"])
    desc_idx = _find_header_index(headers, ["说明", "描述", "description", "desc"])

    # 跳过分隔行（第二行通常是 ---|---|---）
    for row in table_rows[1:]:
        if re.match(r"^[\s|:-]+$", row):
            continue

        cells = [cell.strip() for cell in row.split("|")]
        if len(cells) < 2:
            continue

        param: dict[str, Any] = {"name": cells[name_idx] if name_idx < len(cells) else ""}
        if type_idx < len(cells):
            param["type"] = cells[type_idx]
        if required_idx < len(cells):
            param["required"] = cells[required_idx] in ("是", "必填", "true", "Yes", "Y")
        if desc_idx < len(cells):
            param["description"] = cells[desc_idx]

        params.append(param)

    return params


def _find_header_index(headers: list[str], keywords: list[str]) -> int:
    """查找表头中匹配关键字的列索引"""
    for i, header in enumerate(headers):
        for keyword in keywords:
            if keyword.lower() in header.lower():
                return i
    return 0


def _extract_code_block(text: str, languages: list[str], context_keywords: list[str] | None = None) -> str:
    """提取指定语言和上下文的代码块"""
    # 按代码块分割
    blocks = re.split(r"```", text)

    for i, block in enumerate(blocks):
        lines = block.strip().split("\n")
        if not lines:
            continue

        # 第一行是语言标识
        first_line = lines[0].strip().lower()
        if not any(lang in first_line for lang in languages):
            continue

        # 如果指定了上下文关键字，检查前面的文本
        if context_keywords:
            preceding_text = blocks[i - 1] if i > 0 else ""
            if not any(kw in preceding_text for kw in context_keywords):
                continue

        # 提取代码内容（跳过第一行语言标识）
        code_lines = lines[1:] if first_line else lines
        return "\n".join(code_lines).strip()

    return ""


def _infer_schema(obj: Any) -> dict[str, Any]:
    """从 JSON 示例推断 JSON Schema"""
    if obj is None:
        return {"type": "null"}
    if isinstance(obj, bool):
        return {"type": "boolean"}
    if isinstance(obj, int):
        return {"type": "integer"}
    if isinstance(obj, float):
        return {"type": "number"}
    if isinstance(obj, str):
        return {"type": "string"}
    if isinstance(obj, list):
        item_schema = _infer_schema(obj[0]) if obj else {"type": "string"}
        return {"type": "array", "items": item_schema}
    if isinstance(obj, dict):
        properties = {}
        for key, value in obj.items():
            properties[key] = _infer_schema(value)
        return {"type": "object", "properties": properties}
    return {"type": "string"}
