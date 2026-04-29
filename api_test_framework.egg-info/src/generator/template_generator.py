"""
模板生成器 — 基于结构化接口信息，通过模板生成基础测试用例（降级方案）
保证即使 LLM 不可用也能生成基本可用的测试代码
"""

from __future__ import annotations

import json
from typing import Any

from src.core.types import ApiInfo
from src.parser.normalizer import group_apis_by_tag
from src.utils.logger import logger


def generate_template_test(api: ApiInfo) -> str:
    """
    为单个接口生成基于模板的 pytest 测试代码

    生成策略：
    - 200 正常响应测试
    - 400 参数错误测试（缺少必填字段）
    - 401 未认证测试（如果接口需要认证）
    - 404 资源不存在测试（对 GET/PUT/DELETE 资源型接口）
    """
    method = api.method.value.lower()
    class_name = _to_class_name(api.section or api.tags[0] if api.tags else "default")
    func_prefix = f"{method}_{_to_snake_case(api.name)}"

    lines: list[str] = []
    lines.append(f"import pytest")
    lines.append(f"from src.client import BaseClient")
    lines.append(f"from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time")
    lines.append(f"")
    lines.append(f"")
    lines.append(f'class Test{class_name}API:')
    lines.append(f'    """{api.name} 接口测试（模板生成）"""')
    lines.append(f"")
    lines.append(f"    @pytest.fixture(autouse=True)")
    lines.append(f"    def setup(self, api_client):")
    lines.append(f"        self.client = api_client")
    lines.append(f"")
    lines.append(f"    def test_{func_prefix}_success(self):")
    lines.append(f'        """{api.name} - 正常请求"""')
    lines.append(f"        # Arrange")

    # 构建请求代码
    if method == "get":
        lines.extend(_build_get_request(api))
    elif method == "delete":
        lines.extend(_build_delete_request(api))
    else:
        lines.extend(_build_body_request(api, method))

    lines.append(f"        # Act")
    if method == "get":
        lines.append(f"        resp = self.client.get(")
    elif method == "delete":
        lines.append(f"        resp = self.client.delete(")
    else:
        lines.append(f"        resp = self.client.{method}(")

    lines.append(f'            "{api.path}",')
    if method in ("get", "delete"):
        if api.query_params:
            lines.append(f"            params=params,")
        if api.auth_required:
            lines.append(f"            headers=self.client.auth_headers,")
    else:
        lines.append(f"            json=payload,")
        if api.auth_required:
            lines.append(f"            headers=self.client.auth_headers,")
    lines.append(f"        )")
    lines.append(f"")
    lines.append(f"        # Assert")
    lines.append(f"        assert_status_code(resp, 200)")
    lines.append(f"        assert_response_time(resp, 5000)")
    if api.response_schemas and 200 in api.response_schemas:
        example = api.response_schemas[200].example
        if isinstance(example, dict) and "code" in example:
            lines.append(f'        assert_field_value(resp, "code", 200)')
    lines.append(f"")
    lines.append(f"")
    # 400 测试
    if api.request_body and api.request_body.required_fields:
        missing_field = api.request_body.required_fields[0]
        lines.append(f"    def test_{func_prefix}_missing_required_field(self):")
        lines.append(f'        """{api.name} - 缺少必填字段 {missing_field}"""')
        lines.append(f"        payload = {{}}  # 空请求体")
        lines.append(f"        resp = self.client.{method}(")
        lines.append(f'            "{api.path}",')
        lines.append(f"            json=payload,")
        if api.auth_required:
            lines.append(f"            headers=self.client.auth_headers,")
        lines.append(f"        )")
        lines.append(f"        assert_status_code(resp, 400)")
        lines.append(f"")

    # 401 测试
    if api.auth_required:
        lines.append(f"    def test_{func_prefix}_unauthorized(self):")
        lines.append(f'        """{api.name} - 未认证请求"""')
        lines.append(f"        resp = self.client.{method}(")
        lines.append(f'            "{api.path}",')
        if method in ("get", "delete"):
            lines.append(f"        )")
        else:
            lines.append(f"            json={{}},")
            lines.append(f"        )")
        lines.append(f"        assert_status_code(resp, 401)")
        lines.append(f"")

    # 404 测试（GET/PUT/DELETE 资源型接口）
    if method in ("get", "put", "delete") and _is_resource_endpoint(api.path):
        lines.append(f"    def test_{func_prefix}_not_found(self):")
        lines.append(f'        """{api.name} - 资源不存在"""')
        if method in ("get", "delete"):
            path_404 = _replace_path_id(api.path, "999999")
            lines.append(f"        resp = self.client.{method}(")
            lines.append(f'            "{path_404}",')
            if api.auth_required:
                lines.append(f"            headers=self.client.auth_headers,")
            lines.append(f"        )")
        else:
            path_404 = _replace_path_id(api.path, "999999")
            lines.append(f"        resp = self.client.{method}(")
            lines.append(f'            "{path_404}",')
            lines.append(f"            json={{}},")
            if api.auth_required:
                lines.append(f"            headers=self.client.auth_headers,")
            lines.append(f"        )")
        lines.append(f"        assert_status_code(resp, 404)")
        lines.append(f"")

    return "\n".join(lines)


def generate_template_tests_batch(apis: list[ApiInfo]) -> dict[str, str]:
    """
    批量生成模板测试用例，按分组输出

    Returns:
        {文件名: 文件内容} 映射
    """
    groups = group_apis_by_tag(apis)
    result: dict[str, str] = {}

    for group_name, group_apis in groups.items():
        file_name = f"test_{_to_snake_case(group_name)}_api.py"

        # 合并同组所有接口的测试代码（提取类内部方法）
        class_name = _to_class_name(group_name)
        lines: list[str] = []
        lines.append("import pytest")
        lines.append("from src.client import BaseClient")
        lines.append("from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time")
        lines.append("")
        lines.append("")
        lines.append(f'class Test{class_name}API:')
        lines.append(f'    """{group_name} 接口测试（模板生成）"""')
        lines.append(f"")
        lines.append(f"    @pytest.fixture(autouse=True)")
        lines.append(f"    def setup(self, api_client):")
        lines.append(f"        self.client = api_client")
        lines.append("")

        for api in group_apis:
            method_lines = _extract_test_methods(api, class_name)
            lines.extend(method_lines)

        result[file_name] = "\n".join(lines)
        logger.info(f"模板生成: {file_name} ({len(group_apis)} 个接口)")

    return result


def _extract_test_methods(api: ApiInfo, class_name: str) -> list[str]:
    """从单个接口生成测试方法代码（只提取 def test_ 方法和文档字符串）"""
    full_code = generate_template_test(api)
    lines = full_code.split("\n")
    methods: list[str] = []

    for line in lines:
        stripped = line.strip()

        # 跳过 import、class、setup fixture、空文档字符串行
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        if stripped.startswith("class "):
            continue
        if stripped.startswith("def setup("):
            continue
        if stripped == '"""':
            continue

        # 保留 def test_ 方法
        if stripped.startswith("def test_"):
            methods.append("")
            methods.append(line)
        elif methods and line:
            # 在方法内部的行（已有缩进）
            if methods[-1] == "" and stripped:
                # 文档字符串
                if stripped.startswith('"""'):
                    methods.append("    " + line)
                else:
                    methods[-1] = "    " + line
            else:
                methods.append("    " + line if not line.startswith("    ") else line)

    return methods


def _build_get_request(api: ApiInfo) -> list[str]:
    """构建 GET 请求的参数代码"""
    lines: list[str] = []
    if api.query_params:
        lines.append(f"        params = {{")
        for p in api.query_params:
            example = f'"{p.example}"' if isinstance(p.example, str) else str(p.example or '""')
            lines.append(f'            "{p.name}": {example},')
        lines.append(f"        }}")
    return lines


def _build_delete_request(api: ApiInfo) -> list[str]:
    """构建 DELETE 请求的参数代码"""
    return _build_get_request(api)


def _build_body_request(api: ApiInfo, method: str) -> list[str]:
    """构建带请求体的请求代码"""
    lines: list[str] = []

    if api.request_body and api.request_body.example:
        example_str = json.dumps(api.request_body.example, ensure_ascii=False, indent=12)
        lines.append(f"        payload = {example_str}")
    else:
        lines.append(f"        payload = {{}}  # TODO: 填充请求体")

    return lines


def _to_class_name(name: str) -> str:
    """转换为 PascalCase 类名"""
    return "".join(word.capitalize() for word in _to_snake_case(name).split("_") if word)


def _to_snake_case(name: str) -> str:
    """转换为 snake_case"""
    import re
    # 移除中文和特殊字符
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name).strip("_")
    # 处理驼峰
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _is_resource_endpoint(path: str) -> bool:
    """判断是否是资源型端点（路径包含 {id} 类参数）"""
    import re
    return bool(re.search(r"\{[^}]+\}", path))


def _replace_path_id(path: str, replacement: str) -> str:
    """将路径参数替换为指定值"""
    import re
    return re.sub(r"\{[^}]+\}", replacement, path)
