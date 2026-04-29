"""
测试用例生成 Prompt — 从结构化接口信息生成 pytest 测试代码
"""

from __future__ import annotations

import json

from src.core.types import ApiInfo


GENERATION_SYSTEM_PROMPT = """\
你是一位资深的 API 自动化测试工程师，精通 Python + Pytest + Requests。

你的任务是根据结构化的接口信息生成高质量的 pytest 测试代码。

代码要求：
1. 使用 src/client/base_client.py 中的 BaseClient 发送请求
2. 使用 src/utils/assertions.py 中的自定义断言（assert_status_code, assert_json_schema, assert_field_value 等）
3. 使用 src/models/context.py 中的 TestContext 管理接口依赖和数据传递
4. 每个测试函数使用 pytest.mark 描述标签和优先级
5. 包含正向测试（正常参数）、逆向测试（异常参数）、边界测试
6. 添加清晰的中文注释
7. 使用 pytest.parametrize 实现数据驱动（当有多个测试数据时）
8. 测试函数命名遵循：test_{method}_{接口简称}_{场景描述}

代码模板格式：
```python
import pytest
from src.client import BaseClient
from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time
from src.models.context import TestContext

class Test{Module}API:
    \"\"\"{模块描述}接口测试\"\"\"

    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        self.client = api_client

    def test_{method}_{name}_success(self):
        \"\"\"{接口名称} - 正常请求\"\"\"
        # Arrange
        payload = {{...}}

        # Act
        resp = self.client.post("{path}", json=payload)

        # Assert
        assert_status_code(resp, 200)
        assert_field_value(resp, "{jsonpath}", {expected})
```

只返回 pytest 代码，用 markdown 代码块（```python）包裹，不要包含任何解释说明。\
"""


def build_generation_prompt(
    api_info: ApiInfo,
    context: dict | None = None,
) -> str:
    """
    构建单个接口的测试用例生成提示词

    Args:
        api_info: 结构化接口信息
        context: 上下文信息（如 base_url, 已有的 fixtures 等）

    Returns:
        用户提示词
    """
    parts: list[str] = []

    api_dict = api_info.to_prompt_dict()
    parts.append(f"请为以下接口生成完整的 pytest 测试代码：\n")
    parts.append(f"接口名称: {api_dict['name']}")
    parts.append(f"请求方法: {api_dict['method']}")
    parts.append(f"请求路径: {api_dict['path']}")
    parts.append(f"接口描述: {api_dict['summary']}")
    parts.append(f"需要认证: {'是' if api_dict['auth_required'] else '否'}")
    parts.append(f"标签: {', '.join(api_dict['tags']) if api_dict['tags'] else '无'}")

    if api_dict.get("path_params"):
        parts.append(f"\n路径参数:")
        for p in api_dict["path_params"]:
            parts.append(f"  - {p['name']} ({p['type']}, {'必填' if p['required'] else '可选'})"
                        + (f" 示例: {p['example']}" if p.get("example") else ""))

    if api_dict.get("query_params"):
        parts.append(f"\n查询参数:")
        for p in api_dict["query_params"]:
            parts.append(f"  - {p['name']} ({p['type']}, {'必填' if p['required'] else '可选'})"
                        + (f" 示例: {p['example']}" if p.get("example") else ""))

    if api_dict.get("request_body"):
        rb = api_dict["request_body"]
        parts.append(f"\n请求体 (Content-Type: {rb['content_type']}):")
        if rb.get("required_fields"):
            parts.append(f"  必填字段: {', '.join(rb['required_fields'])}")
        if rb.get("example"):
            parts.append(f"  示例:\n```json\n{json.dumps(rb['example'], ensure_ascii=False, indent=2)}\n```")

    if api_dict.get("response_schemas"):
        parts.append("\n响应格式:")
        for code, schema in api_dict["response_schemas"].items():
            parts.append(f"  - {code}: {schema.get('schema', {}).get('type', 'unknown')}")
            if schema.get("example"):
                parts.append(f"    示例:\n```json\n{json.dumps(schema['example'], ensure_ascii=False, indent=2)}\n```")

    if api_dict.get("examples"):
        examples = api_dict["examples"]
        if examples.get("request_example"):
            parts.append(f"\n请求示例:\n```json\n{json.dumps(examples['request_example'], ensure_ascii=False, indent=2)}\n```")
        if examples.get("response_example"):
            parts.append(f"\n响应示例:\n```json\n{json.dumps(examples['response_example'], ensure_ascii=False, indent=2)}\n```")

    # 上下文信息
    if context:
        if context.get("base_url"):
            parts.append(f"\nBase URL: {context['base_url']}")
        if context.get("available_fixtures"):
            parts.append(f"可用 fixtures: {', '.join(context['available_fixtures'])}")

    parts.append("\n生成要求：")
    parts.append("1. 生成至少 3 个测试用例：正向（成功）+ 逆向（参数校验/异常）+ 边界")
    parts.append("2. 如果接口需要认证，在 setup 中使用 self.client.auth_headers 附加认证头")
    parts.append("3. 对于有多个必填字段的接口，生成参数缺失的测试用例")
    parts.append("4. 代码直接可用，不需要额外修改")
    parts.append("5. 用 markdown 代码块（```python）包裹，不要解释说明")

    return "\n".join(parts)


def build_batch_generation_prompt(
    apis: list[ApiInfo],
    group_name: str,
    context: dict | None = None,
) -> str:
    """
    构建批量生成提示词（一组接口生成一个测试文件）

    Args:
        apis: 同一分组的接口列表
        group_name: 分组名称（作为 test class 名称）
        context: 上下文信息

    Returns:
        用户提示词
    """
    parts: list[str] = []

    parts.append(f"请为「{group_name}」模块的 {len(apis)} 个接口生成完整的 pytest 测试代码。")
    parts.append("将所有接口的测试放在同一个测试类中。")

    for i, api in enumerate(apis, 1):
        api_dict = api.to_prompt_dict()
        parts.append(f"\n--- 接口 {i} ---")
        parts.append(f"名称: {api_dict['name']}")
        parts.append(f"方法: {api_dict['method']}  路径: {api_dict['path']}")
        parts.append(f"描述: {api_dict['summary']}")
        parts.append(f"认证: {'需要' if api_dict['auth_required'] else '不需要'}")

        if api_dict.get("request_body", {}).get("example"):
            parts.append(f"请求体示例: {json.dumps(api_dict['request_body']['example'], ensure_ascii=False)}")

        if api_dict.get("response_schemas"):
            for code, schema in list(api_dict["response_schemas"].items())[:1]:  # 只取第一个响应
                if schema.get("example"):
                    parts.append(f"响应示例 ({code}): {json.dumps(schema['example'], ensure_ascii=False)}")

    if context:
        if context.get("base_url"):
            parts.append(f"\nBase URL: {context['base_url']}")

    parts.append("\n---")
    parts.append("代码要求：")
    parts.append("1. 每个接口至少 3 个测试：正向 + 逆向 + 边界")
    parts.append("2. 使用类级别的 setup fixture")
    parts.append("3. 需要认证的接口使用 self.client.auth_headers")
    parts.append("4. 用 markdown 代码块（```python）包裹，不要解释说明")

    return "\n".join(parts)
