"""
LLM Client — OpenAI 兼容 API 客户端
支持 DeepSeek、通义千问、智谱 GLM 等国产大模型
对标 UI 框架 LlmClient.ts
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from src.core.types import ChatMessage, ChatOptions, ChatResponse, LlmConfig


class LlmError(Exception):
    """LLM 调用异常"""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.name = "LlmError"


class LlmClient:
    """OpenAI 兼容 API 客户端，内置重试 / 超时 / 错误处理"""

    def __init__(self, config: LlmConfig):
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.timeout = config.timeout
        self.max_retries = config.max_retries

    def chat(
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """
        发送聊天请求，支持自动重试和指数退避

        Args:
            messages: 消息列表
            options: 请求选项（温度、最大 token、JSON 模式等）

        Returns:
            ChatResponse

        Raises:
            LlmError: 请求失败或响应异常
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return self._execute_request(messages, options)
            except LlmError as e:
                last_error = e

                # 认证失败、参数错误等不重试
                if e.status_code and e.status_code in (400, 401, 403, 422):
                    raise

                if attempt < self.max_retries:
                    delay = 1000 * (2 ** attempt)
                    print(f"[LLM] 请求失败 ({attempt + 1}/{self.max_retries}): "
                          f"{e}，{delay}ms 后重试...")
                    time.sleep(delay / 1000)

        raise LlmError(
            f"LLM 请求在 {self.max_retries + 1} 次尝试后失败: {last_error}"
        )

    def _execute_request(
        self,
        messages: list[ChatMessage],
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """执行单次 API 请求"""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": options.temperature if options and options.temperature is not None else self.temperature,
            "max_tokens": options.max_tokens if options and options.max_tokens is not None else self.max_tokens,
        }

        # JSON 模式（部分国产模型可能不支持）
        if options and options.json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self.timeout / 1000) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    json=body,
                )

            if response.status_code != 200:
                raise LlmError(
                    f"API 错误 {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )

            data = response.json()
            return self._parse_response(data)

        except LlmError:
            raise
        except httpx.TimeoutException:
            raise LlmError(f"请求超时 ({self.timeout}ms)")
        except httpx.ConnectError as e:
            raise LlmError(f"连接失败: {e}")
        except Exception as e:
            if isinstance(e, LlmError):
                raise
            raise LlmError(f"网络错误: {e}")

    def _parse_response(self, data: dict[str, Any]) -> ChatResponse:
        """解析 OpenAI 兼容格式的响应"""
        try:
            content = data["choices"][0]["message"]["content"]
            if not content:
                raise LlmError("LLM 返回了空内容")

            return ChatResponse(
                content=content,
                model=data.get("model", self.model),
                usage=data.get("usage"),
            )
        except (KeyError, IndexError) as e:
            raise LlmError(f"解析 LLM 响应失败: {e}, 原始响应: {json.dumps(data, ensure_ascii=False)[:200]}")
