"""
Allure 报告增强 — 自动附加请求/响应详情到报告中
"""

from __future__ import annotations

import json
from typing import Any

import allure


def attach_request(
    method: str,
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    body: Any = None,
) -> None:
    """附加请求信息到 Allure 报告"""
    request_info = {
        "method": method.upper(),
        "url": url,
    }
    if headers:
        # 隐藏敏感信息
        safe_headers = {k: _mask_sensitive(v) for k, v in headers.items()}
        request_info["headers"] = safe_headers
    if params:
        request_info["params"] = params
    if body is not None:
        request_info["body"] = body

    allure.attach(
        json.dumps(request_info, ensure_ascii=False, indent=2),
        name="Request",
        attachment_type=allure.attachment_type.JSON,
    )


def attach_response(
    status_code: int,
    headers: dict | None = None,
    body: Any = None,
    elapsed_ms: float = 0,
) -> None:
    """附加响应信息到 Allure 报告"""
    response_info = {
        "status_code": status_code,
        "elapsed_ms": round(elapsed_ms, 2),
    }
    if headers:
        safe_headers = {k: _mask_sensitive(v) for k, v in headers.items()}
        response_info["headers"] = safe_headers
    if body is not None:
        # 截断过大的响应体
        body_str = json.dumps(body, ensure_ascii=False)
        if len(body_str) > 5000:
            body_str = body_str[:5000] + "\n... (truncated)"
        response_info["body"] = json.loads(body_str) if body_str else None

    allure.attach(
        json.dumps(response_info, ensure_ascii=False, indent=2),
        name="Response",
        attachment_type=allure.attachment_type.JSON,
    )


def attach_curl(curl_command: str) -> None:
    """附加 cURL 复现命令到报告"""
    allure.attach(
        curl_command,
        name="cURL",
        attachment_type=allure.attachment_type.TEXT,
    )


def attach_text(content: str, name: str = "Detail") -> None:
    """附加纯文本到报告"""
    allure.attach(content, name=name, attachment_type=allure.attachment_type.TEXT)


def _mask_sensitive(value: str) -> str:
    """遮蔽敏感信息"""
    sensitive_keys = {"authorization", "token", "password", "secret", "api-key", "apikey"}
    return "****" if any(k in value.lower() for k in sensitive_keys) else value
