"""
全局类型定义
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ============================================================
# 接口信息模型
# ============================================================

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ParamStyle(str, Enum):
    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"


class ParamType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class Param:
    """接口参数"""
    name: str
    type: ParamType = ParamType.STRING
    style: ParamStyle = ParamStyle.QUERY
    required: bool = False
    description: str = ""
    default: Any = None
    enum: list[str] = field(default_factory=list)
    example: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)  # min, max, pattern...


@dataclass
class BodySchema:
    """请求体 / 响应体 Schema"""
    content_type: str = "application/json"
    schema: dict[str, Any] = field(default_factory=dict)      # JSON Schema
    example: Any = None
    required_fields: list[str] = field(default_factory=list)


@dataclass
class ApiInfo:
    """结构化接口信息 — 所有解析器统一输出此格式"""
    name: str
    method: HttpMethod
    path: str
    summary: str = ""
    description: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    path_params: list[Param] = field(default_factory=list)
    query_params: list[Param] = field(default_factory=list)
    header_params: list[Param] = field(default_factory=list)
    request_body: BodySchema | None = None
    response_schemas: dict[int, BodySchema] = field(default_factory=dict)  # status_code -> BodySchema
    auth_required: bool = False
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    examples: dict[str, Any] = field(default_factory=dict)  # request_example, response_example
    source: str = ""               # 来源文件
    section: str = ""              # 所属模块/分组

    def to_prompt_dict(self) -> dict[str, Any]:
        """转换为 Prompt 友好的字典（供 AI 用例生成使用）"""
        result: dict[str, Any] = {
            "name": self.name,
            "method": self.method.value,
            "path": self.path,
            "summary": self.summary,
            "description": self.description,
            "auth_required": self.auth_required,
            "tags": self.tags,
        }

        if self.path_params:
            result["path_params"] = [
                {"name": p.name, "type": p.type.value, "required": p.required, "example": p.example}
                for p in self.path_params
            ]

        if self.query_params:
            result["query_params"] = [
                {"name": p.name, "type": p.type.value, "required": p.required, "example": p.example}
                for p in self.query_params
            ]

        if self.request_body:
            result["request_body"] = {
                "content_type": self.request_body.content_type,
                "schema": self.request_body.schema,
                "example": self.request_body.example,
                "required_fields": self.request_body.required_fields,
            }

        if self.response_schemas:
            result["response_schemas"] = {
                str(code): {"schema": schema.schema, "example": schema.example}
                for code, schema in self.response_schemas.items()
            }

        if self.examples:
            result["examples"] = self.examples

        return result


# ============================================================
# 测试用例模型
# ============================================================

class TestCasePriority(str, Enum):
    P0 = "critical"
    P1 = "high"
    P2 = "medium"
    P3 = "low"


class TestCaseCategory(str, Enum):
    SMOKE = "smoke"
    REGRESSION = "regression"
    INTEGRATION = "integration"
    SECURITY = "security"
    PERFORMANCE = "performance"


@dataclass
class TestCase:
    """生成的测试用例"""
    id: str
    name: str
    api_name: str
    description: str = ""
    priority: TestCasePriority = TestCasePriority.P2
    category: TestCaseCategory = TestCaseCategory.REGRESSION
    tags: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    test_code: str = ""               # 生成的 pytest 代码
    source: str = "ai"                # ai / template
    file_path: str = ""               # 输出文件路径


# ============================================================
# LLM 配置 & 消息类型
# ============================================================

@dataclass
class LlmConfig:
    """大模型配置"""
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 8000
    timeout: int = 60000
    max_retries: int = 3


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str          # system / user / assistant
    content: str


@dataclass
class ChatOptions:
    """聊天请求选项"""
    temperature: float | None = None
    max_tokens: int | None = None
    json_mode: bool = False


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    model: str = ""
    usage: dict[str, int] | None = None


@dataclass
class LlmResult:
    """LLM 处理结果（带元信息）"""
    success: bool
    data: Any = None
    error: str = ""
    model: str = ""
    tokens_used: int = 0


# ============================================================
# 框架配置类型
# ============================================================

@dataclass
class FrameworkConfig:
    """合并后的框架完整配置"""
    # 框架基础
    default_timeout: int = 30000
    retry_count: int = 1
    log_level: str = "INFO"
    workers: str = "auto"

    # API 配置（环境相关）
    api_base_url: str = ""
    api_auth_type: str = "bearer"
    api_auth_login_url: str = ""
    api_auth_username: str = ""
    api_auth_password: str = ""
    api_auth_token_path: str = "$.data.token"

    # LLM 配置
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 8000
    llm_timeout: int = 60000
    llm_max_retries: int = 3

    # 解析器配置
    parser_use_llm: bool = False
    parser_default_format: str = "auto"
    parser_output_dir: str = "output/parsed"

    # 生成器配置
    generator_use_llm: bool = False
    generator_output_dir: str = "output/testcases"
    generator_group_by: str = "tag"

    # 报告配置
    report_type: str = "allure"
    report_allure_dir: str = "output/reports/allure"
    report_attach_request: bool = True
    report_attach_response: bool = True
    report_attach_curl: bool = True

    # 环境名称
    env: str = "dev"
