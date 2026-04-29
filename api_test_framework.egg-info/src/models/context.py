"""
测试上下文 — 接口间参数传递和数据共享
"""

from __future__ import annotations

import re
from typing import Any


class TestContext:
    """
    测试上下文存储

    用于：
    - 接口间参数传递（如登录获取的 token）
    - 请求模板中的变量替换
    - 测试数据共享
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """存储一个值"""
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取一个值"""
        return self._store.get(key, default)

    def has(self, key: str) -> bool:
        """检查 key 是否存在"""
        return key in self._store

    def delete(self, key: str) -> None:
        """删除一个值"""
        self._store.pop(key, None)

    def clear(self) -> None:
        """清空所有值"""
        self._store.clear()

    def extract_from_response(
        self,
        response_data: dict,
        jsonpath: str,
        alias: str,
    ) -> Any:
        """
        从响应数据中用 JSONPath 提取值并存入上下文

        Args:
            response_data: 响应 JSON 数据
            jsonpath: JSONPath 表达式（如 $.data.user.id）
            alias: 存储别名

        Returns:
            提取到的值
        """
        from src.utils.extractor import extract_by_jsonpath

        value = extract_by_jsonpath(response_data, jsonpath)
        self._store[alias] = value
        return value

    def render_template(self, template: str | dict | list | Any) -> Any:
        """
        将模板中的 {{var}} 替换为上下文值

        支持字符串、字典、列表的递归替换。

        Args:
            template: 包含 {{var}} 占位符的模板

        Returns:
            替换后的值
        """
        if isinstance(template, str):
            return re.sub(
                r"\{\{(\w+)\}\}",
                lambda m: str(self._store.get(m.group(1), m.group(0))),
                template,
            )
        if isinstance(template, dict):
            return {k: self.render_template(v) for k, v in template.items()}
        if isinstance(template, list):
            return [self.render_template(item) for item in template]
        return template

    def to_dict(self) -> dict[str, Any]:
        """导出所有存储的值"""
        return self._store.copy()

    def __repr__(self) -> str:
        keys = list(self._store.keys())
        return f"TestContext({len(keys)} vars: {keys[:5]}{'...' if len(keys) > 5 else ''})"
