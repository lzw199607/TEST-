import pytest
from src.client import BaseClient
from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time


class Test认证API:
    """认证 接口测试（模板生成）"""

    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        self.client = api_client


    def test_post_login_success(self):
        """login - 正常请求"""
        # Arrange
        payload = {
            "username": "admin",
            "password": "admin123"
    }
        # Act
        resp = self.client.post(
            "/api/auth/login",
            json=payload,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_post_login_missing_required_field(self):
        """login - 缺少必填字段 username"""
        payload = {}  # 空请求体
        resp = self.client.post(
            "/api/auth/login",
            json=payload,
        )
        assert_status_code(resp, 400)

    def test_post_register_success(self):
        """register - 正常请求"""
        # Arrange
        payload = {
            "username": "newuser",
            "password": "123456",
            "email": "new@example.com"
    }
        # Act
        resp = self.client.post(
            "/api/auth/register",
            json=payload,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)

    def test_post_register_missing_required_field(self):
        """register - 缺少必填字段 username"""
        payload = {}  # 空请求体
        resp = self.client.post(
            "/api/auth/register",
            json=payload,
        )
        assert_status_code(resp, 400)