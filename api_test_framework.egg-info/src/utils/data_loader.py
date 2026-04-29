"""
数据加载器 — CSV / JSON / YAML 文件加载 + Pytest 参数化工具
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Generator

import yaml

from src.utils.logger import logger


def load_csv(file_path: str | Path) -> list[dict[str, str]]:
    """
    加载 CSV 文件为字典列表

    Args:
        file_path: CSV 文件路径

    Returns:
        每行数据为一个字典
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV 文件不存在: {path}")

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def load_json(file_path: str | Path) -> Any:
    """
    加载 JSON 文件

    Args:
        file_path: JSON 文件路径

    Returns:
        解析后的 Python 对象
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(file_path: str | Path) -> Any:
    """
    加载 YAML 文件

    Args:
        file_path: YAML 文件路径

    Returns:
        解析后的 Python 对象
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"YAML 文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_data(file_path: str | Path) -> Any:
    """
    自动识别格式加载数据文件

    支持 CSV / JSON / YAML 格式
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".json":
        return load_json(path)
    if suffix in (".yaml", ".yml"):
        return load_yaml(path)

    raise ValueError(f"不支持的数据格式: {suffix}")


def load_testdata_dir(dir_path: str | Path) -> dict[str, Any]:
    """
    加载目录下所有数据文件

    Returns:
        {文件名(不含扩展名): 数据} 映射
    """
    dir_p = Path(dir_path)
    if not dir_p.is_dir():
        return {}

    result: dict[str, Any] = {}
    for file in dir_p.iterdir():
        if file.is_file() and file.suffix.lower() in (".csv", ".json", ".yaml", ".yml"):
            name = file.stem
            try:
                result[name] = load_data(file)
                logger.debug(f"加载数据文件: {file.name}")
            except Exception as e:
                logger.warning(f"加载数据文件失败 ({file.name}): {e}")

    return result


def csv_to_parametrize(
    file_path: str | Path,
    id_col: str | None = None,
) -> tuple[list[str], list[tuple]]:
    """
    将 CSV 数据转换为 pytest.mark.parametrize 格式

    Args:
        file_path: CSV 文件路径
        id_col: 用作测试 ID 的列名（默认使用第一列）

    Returns:
        (列名列表, 参数元组列表)
    """
    rows = load_csv(file_path)
    if not rows:
        return [], []

    headers = list(rows[0].keys())
    argvalues = [tuple(row.values()) for row in rows]

    return headers, argvalues


def json_to_parametrize(
    file_path: str | Path,
    cases_key: str = "cases",
) -> list[dict[str, Any]]:
    """
    将 JSON 测试数据转换为参数化列表

    支持两种格式：
    1. 直接是数组: [{"input": ..., "expected": ...}]
    2. 包装对象: {"cases": [{"input": ..., "expected": ...}], "name": "..."}
    """
    data = load_json(file_path)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and cases_key in data:
        return data[cases_key]

    raise ValueError(f"JSON 数据格式不支持，期望数组或包含 '{cases_key}' 键的对象")


def load_request_template(file_path: str | Path) -> dict[str, Any]:
    """
    加载请求模板文件

    模板中可以使用 {{var}} 占位符，后续由 TestContext.render_template() 替换。
    """
    data = load_data(file_path)
    if not isinstance(data, dict):
        raise ValueError(f"请求模板必须是 JSON 对象，实际类型: {type(data)}")
    return data
