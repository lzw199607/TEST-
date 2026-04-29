"""
WebSocket 客户端封装
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from src.utils.logger import logger


class WebSocketClient:
    """
    WebSocket 客户端封装

    功能：
    - 连接 / 断开
    - 发送消息
    - 等待响应（带超时）
    - 订阅消息断言
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        max_message_size: int = 1024 * 1024,
    ):
        self.url = url
        self.headers = headers or {}
        self.max_message_size = max_message_size
        self._ws = None
        self._received_messages: list[dict] = []
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def received_messages(self) -> list[dict]:
        """获取所有已收到的消息"""
        return self._received_messages.copy()

    async def connect(self) -> None:
        """建立 WebSocket 连接"""
        try:
            import websockets
        except ImportError:
            raise ImportError("请安装 websockets: pip install websockets")

        self._ws = await websockets.connect(
            self.url,
            additional_headers=self.headers,
            max_size=self.max_message_size,
        )
        self._is_connected = True
        self._received_messages = []
        logger.info(f"WebSocket 已连接: {self.url}")

    async def disconnect(self) -> None:
        """断开 WebSocket 连接"""
        if self._ws:
            await self._ws.close()
            self._is_connected = False
            logger.info(f"WebSocket 已断开: {self.url}")

    async def send(self, message: str | dict) -> None:
        """
        发送消息

        Args:
            message: 字符串或字典（自动序列化为 JSON）
        """
        if not self._ws:
            raise RuntimeError("WebSocket 未连接")

        if isinstance(message, dict):
            message = json.dumps(message, ensure_ascii=False)

        await self._ws.send(message)
        logger.debug(f"WebSocket 发送: {message[:200]}")

    async def send_and_wait(
        self,
        message: str | dict,
        timeout: float = 10.0,
        expect_type: str | None = None,
    ) -> dict:
        """
        发送消息并等待响应

        Args:
            message: 要发送的消息
            timeout: 等待超时（秒）
            expect_type: 期望的响应类型（消息中的 type 字段值）

        Returns:
            解析后的 JSON 响应
        """
        await self.send(message)

        while True:
            try:
                response_text = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"等待 WebSocket 响应超时 ({timeout}s)")

            try:
                response = json.loads(response_text)
            except json.JSONDecodeError:
                response = {"raw": response_text}

            self._received_messages.append(response)
            logger.debug(f"WebSocket 收到: {response_text[:200]}")

            # 检查是否是期望类型的响应
            if expect_type is None or response.get("type") == expect_type:
                return response

    async def wait_for_message(
        self,
        timeout: float = 10.0,
        filter_fn: Any | None = None,
    ) -> dict:
        """
        等待接收消息

        Args:
            timeout: 超时时间
            filter_fn: 过滤函数，返回 True 时停止等待

        Returns:
            收到的消息
        """
        while True:
            try:
                text = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"等待 WebSocket 消息超时 ({timeout}s)")

            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                message = {"raw": text}

            self._received_messages.append(message)

            if filter_fn is None or filter_fn(message):
                return message

    async def __aenter__(self) -> WebSocketClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()
