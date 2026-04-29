"""
三层配置合并：全局 settings.yaml → 环境配置 environments/{env}.yaml → CLI 参数
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.core.types import FrameworkConfig, LlmConfig

# 框架根目录
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent.parent


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合并两个字典，override 中的值覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """加载 YAML 文件，不存在返回空字典"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(env: str = "dev", cli_overrides: dict[str, Any] | None = None) -> FrameworkConfig:
    """
    加载并合并三层配置

    Args:
        env: 环境名称（dev / staging / prod）
        cli_overrides: CLI 传入的覆盖参数

    Returns:
        FrameworkConfig 完整配置对象
    """
    configs_dir = FRAMEWORK_ROOT / "configs"

    # 第一层：全局配置
    global_config = _load_yaml(configs_dir / "settings.yaml")

    # 第二层：环境配置
    env_config = _load_yaml(configs_dir / "environments" / f"{env}.yaml")

    # 合并
    merged = _deep_merge(global_config, env_config)

    # 第三层：CLI 覆盖
    if cli_overrides:
        merged = _deep_merge(merged, cli_overrides)

    # 环境变量覆盖（最高优先级）
    merged = _apply_env_overrides(merged)

    return _build_framework_config(merged, env)


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """从环境变量覆盖 LLM 和 API 配置"""
    env_map = {
        "LLM_BASE_URL": ("llm", "base_url"),
        "LLM_API_KEY": ("llm", "api_key"),
        "LLM_MODEL": ("llm", "model"),
        "LLM_TEMPERATURE": ("llm", "temperature", float),
        "LLM_MAX_TOKENS": ("llm", "max_tokens", int),
        "LLM_TIMEOUT": ("llm", "timeout", int),
        "LLM_MAX_RETRIES": ("llm", "max_retries", int),
        "API_BASE_URL": ("api", "base_url"),
    }

    for env_var, path_parts in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            # 解析嵌套路径
            current = config
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # 类型转换
            if len(path_parts) == 3 and callable(path_parts[2]):
                try:
                    value = path_parts[2](value)
                except (ValueError, TypeError):
                    pass

            current[path_parts[-1]] = value

    return config


def _build_framework_config(merged: dict[str, Any], env: str) -> FrameworkConfig:
    """从合并后的字典构建 FrameworkConfig"""
    fw = merged.get("framework", {})
    llm = merged.get("llm", {})
    parser = merged.get("parser", {})
    generator = merged.get("generator", {})
    report = merged.get("report", {})
    api = merged.get("api", {})
    auth = api.get("auth", {})

    return FrameworkConfig(
        # 框架基础
        default_timeout=fw.get("default_timeout", 30000),
        retry_count=fw.get("retry_count", 1),
        log_level=fw.get("log_level", "INFO"),
        workers=fw.get("workers", "auto"),
        # API
        api_base_url=api.get("base_url", ""),
        api_auth_type=auth.get("type", "bearer"),
        api_auth_login_url=auth.get("login_url", ""),
        api_auth_username=auth.get("username", ""),
        api_auth_password=auth.get("password", ""),
        api_auth_token_path=auth.get("token_path", "$.data.token"),
        # LLM
        llm_base_url=llm.get("base_url", "https://api.deepseek.com/v1"),
        llm_api_key=llm.get("api_key", ""),
        llm_model=llm.get("model", "deepseek-chat"),
        llm_temperature=llm.get("temperature", 0.3),
        llm_max_tokens=llm.get("max_tokens", 8000),
        llm_timeout=llm.get("timeout", 60000),
        llm_max_retries=llm.get("max_retries", 3),
        # 解析器
        parser_use_llm=parser.get("use_llm", False),
        parser_default_format=parser.get("default_format", "auto"),
        parser_output_dir=parser.get("output_dir", "output/parsed"),
        # 生成器
        generator_use_llm=generator.get("use_llm", False),
        generator_output_dir=generator.get("output_dir", "output/testcases"),
        generator_group_by=generator.get("group_by", "tag"),
        # 报告
        report_type=report.get("type", "allure"),
        report_allure_dir=report.get("allure_dir", "output/reports/allure"),
        report_attach_request=report.get("attach_request", True),
        report_attach_response=report.get("attach_response", True),
        report_attach_curl=report.get("attach_curl", True),
        # 环境
        env=env,
    )


def build_llm_config(config: FrameworkConfig) -> LlmConfig | None:
    """从 FrameworkConfig 构建 LlmConfig，缺少 API Key 时返回 None"""
    if not config.llm_api_key:
        return None
    return LlmConfig(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        model=config.llm_model,
        temperature=config.llm_temperature,
        max_tokens=config.llm_max_tokens,
        timeout=config.llm_timeout,
        max_retries=config.llm_max_retries,
    )
