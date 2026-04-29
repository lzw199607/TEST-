"""
自定义断言库 — 状态码、JSON Schema、响应时间、字段断言
"""

from __future__ import annotations

import json
import time
from typing import Any

import jsonschema
import requests

from src.utils.logger import logger


class AssertionError(Exception):
    """自定义断言错误"""

    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.details = details
        self.name = "AssertionError"


# ============================================================
# 基础断言
# ============================================================

def assert_status_code(response: requests.Response, expected: int) -> None:
    """
    断言 HTTP 状态码

    Args:
        response: requests.Response 对象
        expected: 期望的状态码
    """
    actual = response.status_code
    if actual != expected:
        details = f"URL: {response.url}\n期望: {expected}\n实际: {actual}\n响应: {response.text[:200]}"
        raise AssertionError(f"状态码不匹配: 期望 {expected}, 实际 {actual}", details)


def assert_success(response: requests.Response) -> None:
    """断言请求成功（2xx 状态码）"""
    if not (200 <= response.status_code < 300):
        details = f"URL: {response.url}\n状态码: {response.status_code}\n响应: {response.text[:200]}"
        raise AssertionError(f"请求失败: HTTP {response.status_code}", details)


def assert_response_time(response: requests.Response, max_ms: int) -> None:
    """
    断言响应时间

    Args:
        response: requests.Response 对象
        max_ms: 最大允许的响应时间（毫秒）
    """
    elapsed_ms = response.elapsed.total_seconds() * 1000
    if elapsed_ms > max_ms:
        details = f"URL: {response.url}\n最大: {max_ms}ms\n实际: {elapsed_ms:.0f}ms"
        raise AssertionError(f"响应超时: {elapsed_ms:.0f}ms > {max_ms}ms", details)


# ============================================================
# JSON 字段断言
# ============================================================

def _get_json_body(response: requests.Response) -> dict:
    """获取响应的 JSON body"""
    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise AssertionError(f"响应不是有效的 JSON: {e}", f"URL: {response.url}\n内容: {response.text[:200]}")


def assert_field_exists(response: requests.Response, jsonpath: str) -> Any:
    """
    断言响应中存在指定字段

    Args:
        response: requests.Response 对象
        jsonpath: 字段路径（如 data.user.id）

    Returns:
        字段值
    """
    from src.utils.extractor import extract_by_jsonpath

    body = _get_json_body(response)
    try:
        value = extract_by_jsonpath(body, jsonpath)
    except (KeyError, IndexError, TypeError) as e:
        raise AssertionError(f"字段不存在: {jsonpath}", f"JSON 路径查找失败: {e}\n响应: {json.dumps(body, ensure_ascii=False)[:200]}")

    if value is None:
        raise AssertionError(f"字段值为 None: {jsonpath}", f"响应: {json.dumps(body, ensure_ascii=False)[:200]}")

    logger.debug(f"字段断言通过: {jsonpath} = {value}")
    return value


def assert_field_value(
    response: requests.Response,
    jsonpath: str,
    expected: Any,
) -> Any:
    """
    断言响应中指定字段的值

    Args:
        response: requests.Response 对象
        jsonpath: 字段路径
        expected: 期望值
    """
    actual = assert_field_exists(response, jsonpath)

    if actual != expected:
        details = f"路径: {jsonpath}\n期望: {expected}\n实际: {actual}"
        raise AssertionError(f"字段值不匹配: {jsonpath}", details)

    logger.debug(f"字段值断言通过: {jsonpath} = {expected}")
    return actual


def assert_field_type(
    response: requests.Response,
    jsonpath: str,
    expected_type: type | str,
) -> Any:
    """
    断言响应中指定字段的类型

    Args:
        response: requests.Response 对象
        jsonpath: 字段路径
        expected_type: 期望类型（type 或字符串 "string"/"integer"/"number"/"boolean"/"array"/"object"）
    """
    actual = assert_field_exists(response, jsonpath)

    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "list": list,
        "dict": dict,
    }

    if isinstance(expected_type, str):
        expected_type = type_map.get(expected_type, str)

    if not isinstance(actual, expected_type):
        details = f"路径: {jsonpath}\n期望类型: {expected_type}\n实际类型: {type(actual)}\n实际值: {actual}"
        raise AssertionError(f"字段类型不匹配: {jsonpath}", details)

    logger.debug(f"字段类型断言通过: {jsonpath} is {expected_type.__name__}")
    return actual


def assert_field_not_empty(response: requests.Response, jsonpath: str) -> Any:
    """断言字段不为空"""
    actual = assert_field_exists(response, jsonpath)

    is_empty = (
        actual is None
        or actual == ""
        or actual == 0
        or (isinstance(actual, (list, dict)) and len(actual) == 0)
    )

    if is_empty:
        details = f"路径: {jsonpath}\n值: {actual}"
        raise AssertionError(f"字段为空: {jsonpath}", details)

    return actual


# ============================================================
# JSON Schema 断言
# ============================================================

def assert_json_schema(response: requests.Response, schema: dict) -> None:
    """
    断言响应符合 JSON Schema

    Args:
        response: requests.Response 对象
        schema: JSON Schema 定义
    """
    body = _get_json_body(response)

    try:
        jsonschema.validate(instance=body, schema=schema)
    except jsonschema.ValidationError as e:
        details = (
            f"URL: {response.url}\n"
            f"Schema 路径: {'.'.join(str(p) for p in e.absolute_path)}\n"
            f"验证消息: {e.message}\n"
            f"响应: {json.dumps(body, ensure_ascii=False)[:300]}"
        )
        raise AssertionError(f"JSON Schema 验证失败: {e.message}", details)

    logger.debug("JSON Schema 验证通过")


# ============================================================
# 数组断言
# ============================================================

def assert_array_length(response: requests.Response, jsonpath: str, expected_length: int) -> Any:
    """断言数组长度"""
    actual = assert_field_exists(response, jsonpath)
    if not isinstance(actual, list):
        raise AssertionError(f"不是数组: {jsonpath}", f"实际类型: {type(actual)}")
    if len(actual) != expected_length:
        raise AssertionError(
            f"数组长度不匹配: {jsonpath}",
            f"期望: {expected_length}, 实际: {len(actual)}",
        )
    return actual


def assert_array_not_empty(response: requests.Response, jsonpath: str) -> Any:
    """断言数组不为空"""
    actual = assert_field_exists(response, jsonpath)
    if not isinstance(actual, list) or len(actual) == 0:
        raise AssertionError(f"数组为空: {jsonpath}")
    return actual


# ============================================================
# 业务断言
# ============================================================

def assert_business_success(response: requests.Response, code_field: str = "code", expected_code: int = 0) -> dict:
    """
    断言业务请求成功（常见格式：{"code": 0, "message": "success", "data": {...}}）

    Args:
        response: requests.Response 对象
        code_field: 业务状态码字段路径
        expected_code: 期望的业务状态码

    Returns:
        响应 JSON 数据
    """
    assert_status_code(response, 200)
    body = _get_json_body(response)

    # 提取业务状态码
    from src.utils.extractor import extract_by_jsonpath
    try:
        biz_code = extract_by_jsonpath(body, code_field)
    except (KeyError, IndexError, TypeError):
        raise AssertionError(f"业务状态码字段不存在: {code_field}", f"响应: {json.dumps(body, ensure_ascii=False)[:200]}")

    if biz_code != expected_code:
        msg = extract_by_jsonpath(body, "message") if "message" in body else ""
        details = f"期望业务码: {expected_code}, 实际: {biz_code}, 消息: {msg}"
        raise AssertionError(f"业务请求失败: {biz_code}", details)

    logger.debug(f"业务断言通过: code={biz_code}")
    return body
