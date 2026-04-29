import pytest
from src.client import BaseClient
from src.utils.assertions import assert_status_code, assert_field_value, assert_response_time


class Test订单API:
    """订单 接口测试（模板生成）"""

    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        self.client = api_client


    def test_get_list_orders_success(self):
        """listOrders - 正常请求"""
        # Arrange
        params = {
            "page": "",
            "size": "",
            "status": "",
        }
        # Act
        resp = self.client.get(
            "/api/orders",
            params=params,
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_get_list_orders_unauthorized(self):
        """listOrders - 未认证请求"""
        resp = self.client.get(
            "/api/orders",
        )
        assert_status_code(resp, 401)

    def test_post_create_order_success(self):
        """createOrder - 正常请求"""
        # Arrange
        payload = {
            "items": [
                        {
                                    "product_id": 1,
                                    "quantity": 2,
                                    "price": 49.95
                        }
            ],
            "remark": "请尽快发货"
    }
        # Act
        resp = self.client.post(
            "/api/orders",
            json=payload,
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)

    def test_post_create_order_missing_required_field(self):
        """createOrder - 缺少必填字段 items"""
        payload = {}  # 空请求体
        resp = self.client.post(
            "/api/orders",
            json=payload,
            headers=self.client.auth_headers,
        )
        assert_status_code(resp, 400)

    def test_post_create_order_unauthorized(self):
        """createOrder - 未认证请求"""
        resp = self.client.post(
            "/api/orders",
            json={},
        )
        assert_status_code(resp, 401)

    def test_get_get_order_success(self):
        """getOrder - 正常请求"""
        # Arrange
        # Act
        resp = self.client.get(
            "/api/orders/{id}",
            headers=self.client.auth_headers,
        )
        # Assert
        assert_status_code(resp, 200)
        assert_response_time(resp, 5000)
        assert_field_value(resp, "code", 200)

    def test_get_get_order_unauthorized(self):
        """getOrder - 未认证请求"""
        resp = self.client.get(
            "/api/orders/{id}",
        )
        assert_status_code(resp, 401)

    def test_get_get_order_not_found(self):
        """getOrder - 资源不存在"""
        resp = self.client.get(
            "/api/orders/999999",
            headers=self.client.auth_headers,
        )
        assert_status_code(resp, 404)