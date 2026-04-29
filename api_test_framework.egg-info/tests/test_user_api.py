"""
用户相关接口测试 — 示例
"""

import pytest
from src.client import BaseClient
from src.utils.assertions import (
    assert_status_code,
    assert_success,
    assert_field_value,
    assert_field_exists,
    assert_field_type,
    assert_response_time,
    assert_business_success,
    assert_array_not_empty,
)
from src.utils.data_loader import load_csv


class TestAuthAPI:
    """认证接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        self.client = api_client

    def test_login_success(self):
        """用户登录 - 正确的用户名和密码"""
        resp = self.client.post(
            "/api/auth/login",
            json_data={"username": "admin", "password": "admin123"},
        )

        assert_success(resp)
        assert_response_time(resp, 5000)
        assert_business_success(resp, code_field="code", expected_code=0)
        assert_field_exists(resp, "data.token")
        assert_field_type(resp, "data.token", str)
        assert_field_value(resp, "data.user.username", "admin")

    def test_login_wrong_password(self):
        """用户登录 - 错误的密码"""
        resp = self.client.post(
            "/api/auth/login",
            json_data={"username": "admin", "password": "wrongpass"},
        )

        assert_status_code(resp, 401)

    def test_login_empty_username(self):
        """用户登录 - 用户名为空"""
        resp = self.client.post(
            "/api/auth/login",
            json_data={"username": "", "password": "admin123"},
        )

        assert_status_code(resp, 401)

    def test_register_success(self):
        """用户注册 - 正常注册"""
        import time
        unique_username = f"testuser_{int(time.time())}"

        resp = self.client.post(
            "/api/auth/register",
            json_data={
                "username": unique_username,
                "password": "123456",
                "email": f"{unique_username}@example.com",
            },
        )

        assert_status_code(resp, 201)
        assert_business_success(resp)
        assert_field_value(resp, "data.username", unique_username)

    def test_register_missing_password(self):
        """用户注册 - 缺少密码"""
        resp = self.client.post(
            "/api/auth/register",
            json_data={"username": "testuser", "email": "test@example.com"},
        )

        assert_status_code(resp, 400)

    def test_register_short_password(self):
        """用户注册 - 密码过短"""
        resp = self.client.post(
            "/api/auth/register",
            json_data={"username": "testuser", "password": "123", "email": "test@example.com"},
        )

        assert_status_code(resp, 400)


class TestUserAPI:
    """用户管理接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.client = auth_client

    def test_list_users_success(self):
        """获取用户列表 - 正常请求"""
        resp = self.client.get("/api/users", params={"page": 1, "size": 10})

        assert_success(resp)
        assert_business_success(resp)
        assert_field_exists(resp, "data.total")
        assert_field_exists(resp, "data.items")
        assert_field_type(resp, "data.items", list)

    def test_list_users_with_keyword(self):
        """获取用户列表 - 按关键词搜索"""
        resp = self.client.get("/api/users", params={"keyword": "admin"})

        assert_success(resp)
        assert_business_success(resp)

    def test_list_users_with_status_filter(self):
        """获取用户列表 - 按状态筛选"""
        resp = self.client.get("/api/users", params={"status": "active"})

        assert_success(resp)
        assert_business_success(resp)

    def test_get_user_detail_success(self):
        """获取用户详情 - 存在的用户"""
        resp = self.client.get("/api/users/1")

        assert_success(resp)
        assert_business_success(resp)
        assert_field_value(resp, "data.id", 1)
        assert_field_value(resp, "data.username", "admin")
        assert_field_type(resp, "data.email", str)

    def test_get_user_detail_not_found(self):
        """获取用户详情 - 不存在的用户"""
        resp = self.client.get("/api/users/999999")

        assert_status_code(resp, 404)

    def test_update_user_success(self):
        """更新用户 - 正常更新"""
        resp = self.client.put(
            "/api/users/1",
            json_data={"nickname": "更新后的昵称"},
        )

        assert_success(resp)
        assert_business_success(resp)

    def test_create_user_success(self):
        """创建用户 - 管理员创建新用户"""
        import time
        resp = self.client.post(
            "/api/users",
            json_data={
                "username": f"new_{int(time.time())}",
                "password": "123456",
                "role": "user",
            },
        )

        assert_status_code(resp, 201)
        assert_field_exists(resp, "data.id")

    def test_delete_user_success(self):
        """删除用户 - 存在的用户"""
        # 先创建
        import time
        create_resp = self.client.post(
            "/api/users",
            json_data={
                "username": f"del_{int(time.time())}",
                "password": "123456",
                "role": "guest",
            },
        )
        assert create_resp.status_code == 201
        user_id = create_resp.json()["data"]["id"]

        # 再删除
        resp = self.client.delete(f"/api/users/{user_id}")
        assert_success(resp)

    def test_delete_user_not_found(self):
        """删除用户 - 不存在的用户"""
        resp = self.client.delete("/api/users/999999")

        assert_status_code(resp, 404)


class TestDataDrivenLogin:
    """数据驱动测试 - 登录接口"""

    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        self.client = api_client

    @pytest.mark.parametrize("username,password,expected_code", [
        ("admin", "admin123", 0),
        ("admin", "wrongpass", 401),
        ("", "admin123", 401),
        ("notexist", "123456", 401),
    ])
    def test_login_scenarios(self, username, password, expected_code):
        """登录场景参数化测试"""
        resp = self.client.post(
            "/api/auth/login",
            json_data={"username": username, "password": password},
        )

        if expected_code == 0:
            assert_business_success(resp)
        else:
            assert_status_code(resp, expected_code)
