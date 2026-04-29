"""
认证管理器 — 自动维护登录态，Token 获取/刷新/自动附加
"""

from __future__ import annotations

from typing import Any

from src.client.base_client import BaseClient
from src.utils.extractor import extract_by_jsonpath
from src.utils.logger import logger


class AuthManager:
    """
    API 认证管理器

    支持多种认证方式：
    - Bearer Token
    - Basic Auth
    - API Key（Header 或 Query）
    - Cookie

    自动 Token 刷新：检测 401 后尝试重新登录。
    """

    def __init__(
        self,
        client: BaseClient,
        auth_type: str = "bearer",
        login_url: str = "",
        username: str = "",
        password: str = "",
        token_path: str = "$.data.token",
        refresh_url: str = "",
        api_key_header: str = "X-API-Key",
        api_key_value: str = "",
    ):
        self.client = client
        self.auth_type = auth_type.lower()
        self.login_url = login_url
        self.username = username
        self.password = password
        self.token_path = token_path
        self.refresh_url = refresh_url
        self.api_key_header = api_key_header
        self.api_key_value = api_key_value

        # 缓存的认证信息
        self._token: str = ""
        self._refresh_token: str = ""
        self._is_authenticated: bool = False

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @property
    def token(self) -> str:
        return self._token

    def login(self) -> None:
        """
        执行登录，获取认证 Token

        根据认证类型调用不同的登录逻辑。
        """
        if self.auth_type == "bearer":
            self._login_bearer()
        elif self.auth_type == "basic":
            self._login_basic()
        elif self.auth_type == "api_key":
            self._login_api_key()
        elif self.auth_type == "cookie":
            self._login_bearer()  # Cookie 认证通常也是通过登录接口
        else:
            raise ValueError(f"不支持的认证类型: {self.auth_type}")

        self._is_authenticated = True
        logger.info(f"认证成功 (类型: {self.auth_type})")

    def refresh(self) -> None:
        """刷新 Token"""
        if not self.refresh_url:
            logger.warning("未配置刷新接口，将重新登录")
            self.login()
            return

        try:
            resp = self.client.post(
                self.refresh_url,
                json_data={"refresh_token": self._refresh_token},
            )
            if resp.status_code == 200:
                data = resp.json()
                new_token = extract_by_jsonpath(data, self.token_path)
                if new_token:
                    self._token = str(new_token)
                    self.client.set_auth_headers({"Authorization": f"Bearer {self._token}"})
                    logger.info("Token 刷新成功")
                    return
        except Exception as e:
            logger.warning(f"Token 刷新失败: {e}")

        # 刷新失败，重新登录
        logger.info("Token 刷新失败，重新登录...")
        self.login()

    def should_refresh(self, response: Any) -> bool:
        """判断是否需要刷新认证"""
        if hasattr(response, "status_code") and response.status_code == 401:
            return True
        return False

    def handle_401(self, response: Any) -> bool:
        """
        处理 401 响应，尝试自动刷新 Token

        Returns:
            True 表示已刷新，调用方应重试请求
        """
        if not self.should_refresh(response):
            return False

        try:
            self.refresh()
            return True
        except Exception as e:
            logger.error(f"自动刷新失败: {e}")
            return False

    def _login_bearer(self) -> None:
        """Bearer Token 登录"""
        if not self.login_url:
            raise ValueError("Bearer 认证需要配置 login_url")

        payload: dict[str, str] = {}
        if self.username and self.password:
            payload = {"username": self.username, "password": self.password}

        resp = self.client.post(self.login_url, json_data=payload)

        if resp.status_code != 200:
            raise RuntimeError(
                f"登录失败: HTTP {resp.status_code}, "
                f"响应: {resp.text[:200]}"
            )

        data = resp.json()
        token = extract_by_jsonpath(data, self.token_path)

        if not token:
            raise RuntimeError(
                f"无法从响应中提取 Token (路径: {self.token_path}), "
                f"响应: {resp.text[:200]}"
            )

        self._token = str(token)
        self.client.set_auth_headers({"Authorization": f"Bearer {self._token}"})

        # 尝试提取 refresh_token
        refresh_path = self.token_path.replace("token", "refresh_token")
        if refresh_path != self.token_path:
            rt = extract_by_jsonpath(data, refresh_path)
            if rt:
                self._refresh_token = str(rt)

    def _login_basic(self) -> None:
        """Basic Auth 认证"""
        import base64
        if not self.username or not self.password:
            raise ValueError("Basic 认证需要配置 username 和 password")

        credentials = base64.b64encode(
            f"{self.username}:{self.password}".encode("utf-8")
        ).decode("utf-8")
        self.client.set_auth_headers({"Authorization": f"Basic {credentials}"})

    def _login_api_key(self) -> None:
        """API Key 认证"""
        if not self.api_key_value:
            raise ValueError("API Key 认证需要配置 api_key_value")

        self.client.set_auth_headers({self.api_key_header: self.api_key_value})

    def logout(self) -> None:
        """登出，清除认证信息"""
        self._token = ""
        self._refresh_token = ""
        self._is_authenticated = False
        self.client.clear_auth_headers()
        logger.info("已登出")
