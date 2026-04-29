"""
HTTP 客户端封装 — 基于 requests.Session
统一请求日志、超时、重试、错误处理
"""

from __future__ import annotations

import json
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.logger import logger


class BaseClient:
    """
    封装 requests.Session 的 HTTP 客户端

    功能：
    - 自动附加认证头
    - 统一请求/响应日志
    - 自动重试（可配置次数）
    - 超时控制
    - 响应包装
    """

    def __init__(
        self,
        base_url: str = "",
        default_timeout: int = 30000,
        retry_count: int = 1,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_timeout = default_timeout / 1000  # 转换为秒
        self.verify_ssl = verify_ssl
        self._auth_headers: dict[str, str] = {}

        # 创建 Session，配置重试策略
        self.session = requests.Session()
        if retry_count > 0:
            retry_strategy = Retry(
                total=retry_count + 1,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

        # 默认请求头
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    @property
    def auth_headers(self) -> dict[str, str]:
        """获取当前认证头"""
        return self._auth_headers.copy()

    def set_auth_headers(self, headers: dict[str, str]) -> None:
        """设置认证头（用于后续所有请求自动附加）"""
        self._auth_headers = headers
        self.session.headers.update(headers)

    def clear_auth_headers(self) -> None:
        """清除认证头"""
        self._auth_headers = {}
        for key in self._auth_headers:
            self.session.headers.pop(key, None)

    def _build_url(self, path: str) -> str:
        """构建完整 URL"""
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}{path}"

    def _log_request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
    ) -> None:
        """记录请求日志"""
        log_parts = [f">>> {method.upper()} {url}"]
        if headers:
            log_parts.append(f"    Headers: {json.dumps(dict(headers), ensure_ascii=False)}")
        if params:
            log_parts.append(f"    Params: {json.dumps(dict(params), ensure_ascii=False)}")
        if json_data:
            body_str = json.dumps(json_data, ensure_ascii=False)
            if len(body_str) > 500:
                body_str = body_str[:500] + "... (truncated)"
            log_parts.append(f"    Body: {body_str}")
        logger.debug("\n".join(log_parts))

    def _log_response(self, resp: requests.Response, elapsed_ms: float) -> None:
        """记录响应日志"""
        log_parts = [
            f"<<< {resp.status_code} {resp.reason}",
            f"    URL: {resp.url}",
            f"    Time: {elapsed_ms:.0f}ms",
        ]
        try:
            body = resp.json()
            body_str = json.dumps(body, ensure_ascii=False)
            if len(body_str) > 500:
                body_str = body_str[:500] + "... (truncated)"
            log_parts.append(f"    Body: {body_str}")
        except Exception:
            log_parts.append(f"    Body: (non-JSON, {len(resp.content)} bytes)")

        if resp.status_code >= 400:
            logger.warning("\n".join(log_parts))
        else:
            logger.debug("\n".join(log_parts))

    def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_data: dict | None = None,
        data: str | bytes | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: 请求路径（相对或绝对 URL）
            params: 查询参数
            json_data: JSON 请求体
            data: 原始请求体
            headers: 额外请求头
            timeout: 超时时间（秒）

        Returns:
            requests.Response
        """
        url = self._build_url(path)
        timeout = timeout or self.default_timeout

        # 合并 headers（不覆盖 session 级别的认证头）
        merged_headers = {}
        if headers:
            merged_headers.update(headers)

        self._log_request(method, url, params, json_data, merged_headers)

        start_time = time.time()
        resp = self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json_data,
            data=data,
            headers=merged_headers if merged_headers else None,
            timeout=timeout,
            verify=self.verify_ssl,
            **kwargs,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        self._log_response(resp, elapsed_ms)

        return resp

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """GET 请求"""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        """POST 请求"""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        """PUT 请求"""
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        """DELETE 请求"""
        return self.request("DELETE", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        """PATCH 请求"""
        return self.request("PATCH", path, **kwargs)

    def to_curl(self, resp: requests.Response) -> str:
        """将请求转换为 cURL 命令（用于调试和报告）"""
        request = resp.request
        parts = ["curl -X", request.method]

        # URL
        parts.append(f'"{request.url}"')

        # Headers
        for key, value in request.headers.items():
            parts.append(f'-H "{key}: {value}"')

        # Body
        if request.body:
            try:
                body_json = json.loads(request.body)
                body_str = json.dumps(body_json, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                body_str = request.body.decode("utf-8", errors="replace") if isinstance(request.body, bytes) else str(request.body)
            parts.append(f"-d '{body_str}'")

        return " ".join(parts)

    def close(self) -> None:
        """关闭 Session"""
        self.session.close()
