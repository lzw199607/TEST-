"""
JSONPath 响应数据提取工具
"""

from __future__ import annotations

from typing import Any


def extract_by_jsonpath(data: Any, path: str) -> Any:
    """
    使用简化的 JSONPath 表达式从数据中提取值

    支持的语法：
    - $.data.token        → 顶层 data 下的 token
    - $.data.user.id      → 嵌套字段
    - $.data.items[0]     → 数组索引
    - $.data.items[0].name → 混合路径
    - code                → 简单字段名（无 $ 前缀）

    Args:
        data: JSON 数据（dict/list）
        path: JSONPath 表达式

    Returns:
        提取到的值

    Raises:
        KeyError: 路径不存在
    """
    if not path:
        return data

    # 移除前导 $.
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]
    elif path.startswith("."):
        path = path[1:]

    current = data

    # 解析路径段
    segments = _parse_path(path)

    for segment in segments:
        if current is None:
            raise KeyError(f"路径中遇到 None: {path}")

        if isinstance(segment, int):
            # 数组索引
            if isinstance(current, list):
                if segment >= len(current):
                    raise IndexError(f"数组索引越界: [{segment}], 长度: {len(current)}")
                current = current[segment]
            else:
                raise TypeError(f"期望列表但得到 {type(current).__name__}: [{segment}]")
        else:
            # 字典键
            if isinstance(current, dict):
                if segment not in current:
                    raise KeyError(f"字段不存在: '{segment}', 可用字段: {list(current.keys())[:5]}")
                current = current[segment]
            else:
                raise TypeError(f"期望字典但得到 {type(current).__name__}: '{segment}'")

    return current


def _parse_path(path: str) -> list[str | int]:
    """
    将路径字符串解析为段列表

    "data.user.items[0].name" → ["data", "user", "items", 0, "name"]
    """
    segments: list[str | int] = []
    current = ""

    i = 0
    while i < len(path):
        char = path[i]

        if char == ".":
            if current:
                segments.append(current)
                current = ""
        elif char == "[":
            if current:
                segments.append(current)
                current = ""
            # 读取数组索引
            j = i + 1
            while j < len(path) and path[j] != "]":
                j += 1
            index_str = path[i + 1 : j]
            try:
                segments.append(int(index_str))
            except ValueError:
                segments.append(index_str)
            i = j
        else:
            current += char

        i += 1

    if current:
        segments.append(current)

    return segments


def extract_all(data: Any, path: str) -> list[Any]:
    """
    提取所有匹配路径的值（用于数组场景）

    如果路径的某一段指向数组，会遍历所有元素。
    """
    results: list[Any] = []

    try:
        value = extract_by_jsonpath(data, path)
        if isinstance(value, list):
            results.extend(value)
        else:
            results.append(value)
    except (KeyError, IndexError, TypeError):
        pass

    return results
