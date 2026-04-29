"""
WebSocket 接口测试 — 示例
需要 WebSocket 服务端支持
"""

import pytest
import asyncio

from src.client.ws_client import WebSocketClient


@pytest.mark.skip(reason="需要 WebSocket 服务端支持")
class TestWebSocket:
    """WebSocket 接口测试"""

    @pytest.mark.asyncio
    async def test_ws_connect(self):
        """WebSocket 连接测试"""
        async with WebSocketClient("ws://localhost:8080/ws") as ws:
            assert ws.is_connected

    @pytest.mark.asyncio
    async def test_ws_send_and_receive(self):
        """WebSocket 发送并接收消息"""
        async with WebSocketClient("ws://localhost:8080/ws") as ws:
            response = await ws.send_and_wait(
                {"type": "ping", "data": "hello"},
                timeout=5.0,
            )
            assert response.get("type") == "pong"
