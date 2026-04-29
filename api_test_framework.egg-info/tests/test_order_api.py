"""
订单相关接口测试 — 示例
"""

import pytest
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
from src.utils.data_loader import load_json
from pathlib import Path

# 加载订单创建测试数据
ORDER_TEST_DATA = Path(__file__).parent.parent / "data" / "testcases" / "create_order.json"


class TestOrderAPI:
    """订单接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.client = auth_client

    def test_list_orders_success(self):
        """获取订单列表 - 正常请求"""
        resp = self.client.get("/api/orders", params={"page": 1, "size": 10})

        assert_success(resp)
        assert_business_success(resp)
        assert_field_type(resp, "data.items", list)

    def test_list_orders_with_status_filter(self):
        """获取订单列表 - 按状态筛选"""
        resp = self.client.get("/api/orders", params={"status": "paid"})

        assert_success(resp)
        assert_business_success(resp)

    def test_create_order_success(self):
        """创建订单 - 正常下单"""
        resp = self.client.post(
            "/api/orders",
            json_data={
                "items": [{"product_id": 1, "quantity": 2, "price": 49.95}],
                "remark": "请尽快发货",
            },
        )

        assert_status_code(resp, 201)
        assert_business_success(resp)
        assert_field_exists(resp, "data.order_id")
        assert_field_type(resp, "data.order_id", str)
        assert_field_value(resp, "data.status", "pending")

    def test_get_order_detail_success(self):
        """获取订单详情 - 存在的订单"""
        # 先创建订单
        create_resp = self.client.post(
            "/api/orders",
            json_data={
                "items": [{"product_id": 1, "quantity": 1, "price": 49.95}],
            },
        )
        if create_resp.status_code == 201:
            order_id = create_resp.json()["data"]["order_id"]

            resp = self.client.get(f"/api/orders/{order_id}")
            assert_success(resp)
            assert_business_success(resp)
            assert_field_value(resp, "data.id", order_id)
            assert_array_not_empty(resp, "data.items")
        else:
            pytest.skip("创建订单失败，跳过详情测试")

    def test_get_order_detail_not_found(self):
        """获取订单详情 - 不存在的订单"""
        resp = self.client.get("/api/orders/NONEXIST123")

        assert_status_code(resp, 404)


class TestOrderDataDriven:
    """订单接口 - 数据驱动测试"""

    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.client = auth_client

    @pytest.mark.parametrize("case", load_json(ORDER_TEST_DATA).get("cases", []))
    def test_create_order_scenarios(self, case):
        """创建订单 - 多种场景"""
        resp = self.client.post(
            "/api/orders",
            json_data={
                "items": case["items"],
                "remark": case.get("remark", ""),
            },
        )

        expected_code = case.get("expected_code", 0)
        if expected_code == 0:
            assert_business_success(resp)
            if "expected_status" in case:
                assert_field_value(resp, "data.status", case["expected_status"])
        else:
            assert_status_code(resp, expected_code)
