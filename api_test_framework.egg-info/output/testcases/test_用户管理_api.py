import pytest
from src.client import BaseClient
from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time


class Test用户管理API:
    """用户管理 接口测试（模板生成）"""

    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        self.client = api_client


    def test_get_list_users_success(self):
        """listUsers - 正常请求"""
        # Arrange
        params = {
            "page": "",
            "size": "",
            "keyword": "",
            "status": "",
        }
        # Act
        resp = self.client.get(
            "/api/users",
            params=params,
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_get_list_users_unauthorized(self):
        """listUsers - 未认证请求"""
        resp = self.client.get(
            "/api/users",
        )
        assert_status_code(resp, 401)

    def test_post_create_user_success(self):
        """createUser - 正常请求"""
        # Arrange
        payload = {
            "username": "testuser",
            "password": "123456",
            "role": "user"
    }
        # Act
        resp = self.client.post(
            "/api/users",
            json=payload,
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)

    def test_post_create_user_missing_required_field(self):
        """createUser - 缺少必填字段 username"""
        payload = {}  # 空请求体
        resp = self.client.post(
            "/api/users",
            json=payload,
            headers=self.client.auth_headers,
        )
        assert_status_code(resp, 400)

    def test_post_create_user_unauthorized(self):
        """createUser - 未认证请求"""
        resp = self.client.post(
            "/api/users",
            json={},
        )
        assert_status_code(resp, 401)

    def test_get_get_user_success(self):
        """getUser - 正常请求"""
        # Arrange
        # Act
        resp = self.client.get(
            "/api/users/{id}",
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_get_get_user_unauthorized(self):
        """getUser - 未认证请求"""
        resp = self.client.get(
            "/api/users/{id}",
        )
        assert_status_code(resp, 401)

    def test_get_get_user_not_found(self):
        """getUser - 资源不存在"""
        resp = self.client.get(
            "/api/users/999999",
            headers=self.client.auth_headers,
        )
        assert_status_code(resp, 404)

    def test_put_update_user_success(self):
        """updateUser - 正常请求"""
        # Arrange
        payload = {
            "nickname": "新昵称",
            "email": "new@example.com"
    }
        # Act
        resp = self.client.put(
            "/api/users/{id}",
            json=payload,
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_put_update_user_unauthorized(self):
        """updateUser - 未认证请求"""
        resp = self.client.put(
            "/api/users/{id}",
            json={},
        )
        assert_status_code(resp, 401)

    def test_put_update_user_not_found(self):
        """updateUser - 资源不存在"""
        resp = self.client.put(
            "/api/users/999999",
            json={},
            headers=self.client.auth_headers,
        )
        assert_status_code(resp, 404)

    def test_delete_delete_user_success(self):
        """deleteUser - 正常请求"""
        # Arrange
        # Act
        resp = self.client.delete(
            "/api/users/{id}",
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_delete_delete_user_unauthorized(self):
        """deleteUser - 未认证请求"""
        resp = self.client.delete(
            "/api/users/{id}",
        )
        assert_status_code(resp, 401)

    def test_delete_delete_user_not_found(self):
        """deleteUser - 资源不存在"""
        resp = self.client.delete(
            "/api/users/999999",
            headers=self.client.auth_headers,
        )
        assert_status_code(resp, 404)