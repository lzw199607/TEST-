"""
全局 Pytest Fixtures — Session 级别的共享资源
"""

from __future__ import annotations

import pytest

from src.client.auth_manager import AuthManager
from src.client.base_client import BaseClient
from src.core.config import load_config
from src.core.types import FrameworkConfig
from src.models.context import TestContext


@pytest.fixture(scope="session")
def framework_config() -> FrameworkConfig:
    """加载框架配置（从环境变量获取 --env 参数）"""
    import os
    env = os.environ.get("API_TEST_ENV", "dev")
    return load_config(env)


@pytest.fixture(scope="session")
def api_client(framework_config: FrameworkConfig) -> BaseClient:
    """
    创建 HTTP 客户端实例

    已配置 base_url、超时、重试策略。
    需要认证时使用 auth_client fixture。
    """
    client = BaseClient(
        base_url=framework_config.api_base_url,
        default_timeout=framework_config.default_timeout,
        retry_count=framework_config.retry_count,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def auth_client(
    framework_config: FrameworkConfig,
    api_client: BaseClient,
) -> BaseClient:
    """
    创建已认证的 HTTP 客户端

    自动执行登录并附加认证头。
    如果登录配置缺失，则退化为未认证客户端。
    """
    if not framework_config.api_auth_login_url:
        yield api_client
        return

    try:
        auth_manager = AuthManager(
            client=api_client,
            auth_type=framework_config.api_auth_type,
            login_url=framework_config.api_auth_login_url,
            username=framework_config.api_auth_username,
            password=framework_config.api_auth_password,
            token_path=framework_config.api_auth_token_path,
        )
        auth_manager.login()
        yield api_client
    except Exception as e:
        import warnings
        warnings.warn(f"认证失败，使用未认证客户端: {e}")
        yield api_client


@pytest.fixture(scope="function")
def test_context() -> TestContext:
    """
    创建测试上下文（函数级别）

    每个测试函数获得独立的上下文实例，用于接口间参数传递。
    """
    ctx = TestContext()
    yield ctx


@pytest.fixture(scope="session")
def config(framework_config: FrameworkConfig) -> dict:
    """配置字典（便捷访问）"""
    return {
        "base_url": framework_config.api_base_url,
        "env": framework_config.env,
        "timeout": framework_config.default_timeout,
    }
