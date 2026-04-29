"""
接口信息提取 Prompt — 从文档中提取结构化接口信息
"""

from __future__ import annotations


API_EXTRACTION_SYSTEM_PROMPT = """\
你是一位资深的 API 接口分析师，擅长从各种格式的文档中提取结构化接口信息。

你的任务是从文档中识别并提取所有 API 接口，输出标准化的 JSON 格式。

提取规则：
1. 识别所有 HTTP 接口（GET/POST/PUT/DELETE/PATCH）
2. 提取完整的请求路径、方法、参数、请求体、响应格式
3. 识别接口之间的认证要求
4. 按功能模块对接口进行分组（tags）
5. 提取请求和响应的示例数据
6. 注意区分路径参数（如 /users/{id} 中的 id）和查询参数

输出格式：JSON 对象，包含一个 "apis" 字段（数组），每个接口包含以下字段：
- name: string — 接口名称
- method: string — HTTP 方法（GET/POST/PUT/DELETE/PATCH）
- path: string — 请求路径（如 /api/users/{id}）
- summary: string — 接口描述（一行摘要）
- path_params: array — 路径参数列表，每个参数: {name, type, required, description, example}
- query_params: array — 查询参数列表，每个参数: {name, type, required, description, example}
- header_params: array — 请求头参数列表
- request_body: object 或 null — 请求体（含 schema、example、required_fields）
- response_schemas: object — 响应定义，key 为 HTTP 状态码字符串（如 "200"），value 为 schema
- auth_required: boolean — 是否需要认证
- tags: array — 标签数组（功能分组）
- examples: object — 请求/响应示例（request_example, response_example）
- section: string — 所属模块/分组名称

如果文档中没有明确的接口定义，请根据文档中描述的功能推导出合理的 RESTful API 设计。
只返回有效的 JSON，不要包含 markdown 格式或解释说明。
"""


def build_api_extraction_prompt(content: str, source: str = "") -> str:
    """
    构建文档解析的用户提示词

    Args:
        content: 文档文本内容
        source: 文档来源文件名

    Returns:
        用户提示词
    """
    parts: list[str] = []

    parts.append("请从以下文档中提取所有 API 接口信息。")

    if source:
        parts.append(f"文档名称: {source}")

    # 截断过长的文档
    max_length = 15000
    if len(content) > max_length:
        parts.append(f"文档较长，已截取前 {max_length} 字符：")
        parts.append("---")
        parts.append(content[:max_length])
        parts.append("---")
        parts.append("... [文档已截断，请基于以上内容提取] ...")
    else:
        parts.append("---")
        parts.append(content)
        parts.append("---")

    parts.append("提取要求：")
    parts.append("1. 提取所有可见的 API 接口定义")
    parts.append("2. 包含完整的参数信息（类型、是否必填、示例值）")
    parts.append("3. 保留请求和响应的示例数据")
    parts.append("4. 合理分组（按业务模块打标签）")
    parts.append("5. 只返回有效的 JSON，不要包含 markdown 格式或解释说明")

    return "\n".join(parts)
