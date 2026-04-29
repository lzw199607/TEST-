"""
CLI 入口 — api-test 命令行工具
对标 UI 框架 cli.ts 的命令结构

命令：
  api-test parse <doc>    解析接口文档
  api-test generate <dir> 生成测试用例
  api-test run [dir]       执行测试
  api-test report          查看报告
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import click
from rich.console import Console
from rich.table import Table

from src.core.config import FRAMEWORK_ROOT, build_llm_config, load_config
from src.core.llm_client import LlmClient
from src.utils.logger import logger, setup_logger

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="api-test")
@click.option("--env", default="dev", help="环境名称 (dev/staging/prod)")
@click.option("--verbose", "-v", is_flag=True, help="详细日志输出")
@click.pass_context
def cli(ctx: click.Context, env: str, verbose: bool) -> None:
    """AI + 接口自动化测试框架"""
    ctx.ensure_object(dict)
    ctx.obj["env"] = env

    # 初始化日志
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(level=log_level)


# ============================================================
# parse 命令
# ============================================================

@cli.command()
@click.argument("doc_path", type=click.Path(exists=True))
@click.option("--format", "format_hint", default="auto",
              type=click.Choice(["auto", "openapi", "apifox", "markdown"]),
              help="文档格式（默认自动识别）")
@click.option("--llm/--no-llm", default=False, help="启用 AI 辅助解析")
@click.pass_context
def parse(ctx: click.Context, doc_path: str, format_hint: str, llm: bool) -> None:
    """解析接口文档，输出结构化接口列表"""
    env = ctx.obj["env"]
    config = load_config(env)

    llm_client = _get_llm_client(config, llm, "--llm")

    from src.parser.doc_parser import parse_document

    try:
        apis = parse_document(doc_path, format_hint, llm, llm_client)
    except Exception as e:
        console.print(f"[red]解析失败: {e}[/red]")
        sys.exit(1)

    if not apis:
        console.print("[yellow]未找到任何接口信息[/yellow]")
        return

    # 显示结果表格
    table = Table(title=f"解析结果 ({len(apis)} 个接口)")
    table.add_column("接口名称", style="cyan")
    table.add_column("方法", style="green")
    table.add_column("路径", style="blue")
    table.add_column("认证", style="yellow")
    table.add_column("标签")

    for api in apis:
        table.add_row(
            api.name,
            api.method.value,
            api.path,
            "是" if api.auth_required else "否",
            ", ".join(api.tags) if api.tags else "-",
        )

    console.print(table)

    # 保存解析结果
    output_dir = Path(config.parser_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"parsed_apis.json"

    import json
    apis_data = [api.to_prompt_dict() for api in apis]
    output_file.write_text(json.dumps(apis_data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[dim]解析结果已保存: {output_file}[/dim]")


# ============================================================
# generate 命令
# ============================================================

@cli.command()
@click.argument("doc_dir", type=click.Path(exists=True))
@click.option("--llm/--no-llm", default=False, help="启用 AI 生成测试用例")
@click.option("--output-dir", default=None, help="输出目录（默认使用配置中的路径）")
@click.pass_context
def generate(ctx: click.Context, doc_dir: str, llm: bool, output_dir: str | None) -> None:
    """从接口文档生成 pytest 测试用例"""
    env = ctx.obj["env"]
    config = load_config(env)

    llm_client = _get_llm_client(config, llm, "--llm")

    # 强制启用 LLM 如果指定了 --llm
    if llm:
        config.generator_use_llm = True

    from src.parser.doc_parser import parse_directory
    from src.generator.test_generator import generate_testcases

    # 解析文档
    with console.status("[bold green]正在解析接口文档..."):
        apis = parse_directory(doc_dir, use_llm=llm, llm_client=llm_client)

    if not apis:
        console.print("[yellow]未找到任何接口信息，无法生成测试用例[/yellow]")
        return

    console.print(f"[green]已解析 {len(apis)} 个接口，开始生成测试用例...[/green]")

    # 生成测试用例
    with console.status("[bold green]正在生成测试用例..."):
        result = generate_testcases(apis, config, output_dir, llm_client)

    if result:
        table = Table(title=f"生成结果 ({len(result)} 个文件)")
        table.add_column("文件名", style="cyan")
        table.add_column("路径", style="blue")
        for name, path in result.items():
            table.add_row(name, path)
        console.print(table)
        console.print(f"\n[green]测试用例生成完成！[/green]")
        console.print(f"[dim]执行命令运行测试: api-test run {output_dir or config.generator_output_dir}[/dim]")
    else:
        console.print("[red]测试用例生成失败[/red]")
        sys.exit(1)


# ============================================================
# run 命令
# ============================================================

@cli.command()
@click.argument("test_dir", default=None, required=False)
@click.option("--env", "env_override", default=None, help="覆盖环境配置")
@click.option("--tags", default=None, help="按标签过滤（逗号分隔）")
@click.option("--allure", "use_allure", is_flag=True, help="生成 Allure 报告")
@click.option("--workers", "-w", default=None, help="并行 worker 数量")
@click.option("--headed", is_flag=True, help="显示测试输出（非静默模式）")
@click.pass_context
def run(ctx: click.Context, test_dir: str | None, env_override: str | None,
        tags: str | None, use_allure: bool, workers: str | None, headed: bool) -> None:
    """执行测试"""
    import subprocess

    env = env_override or ctx.obj["env"]
    config = load_config(env)

    test_path = test_dir or config.generator_output_dir
    if not Path(test_path).exists():
        console.print(f"[red]测试目录不存在: {test_path}[/red]")
        sys.exit(1)

    # 构建 pytest 命令
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",
        "--tb=short",
    ]

    # Allure
    allure_dir = config.report_allure_dir
    Path(allure_dir).mkdir(parents=True, exist_ok=True)
    if use_allure:
        cmd.extend(["--alluredir", allure_dir])

    # 标签过滤
    if tags:
        for tag in tags.split(","):
            cmd.extend(["-k", tag.strip()])

    # 并行执行
    if workers:
        cmd.extend(["-n", workers])
    elif config.workers != "auto":
        cmd.extend(["-n", config.workers])

    console.print(f"[bold]执行测试: {' '.join(cmd)}[/bold]\n")

    # 设置环境变量
    import os
    env_vars = os.environ.copy()
    env_vars["API_TEST_ENV"] = env

    # 执行
    result = subprocess.run(cmd, env=env_vars, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        console.print("\n[red]测试执行失败[/red]")
        sys.exit(result.returncode)
    else:
        console.print("\n[green]测试执行完成[/green]")
        if use_allure:
            console.print(f"[dim]查看报告: api-test report --allure-dir {allure_dir}[/dim]")


# ============================================================
# report 命令
# ============================================================

@cli.command()
@click.option("--allure-dir", default=None, help="Allure 报告目录")
@click.option("--serve", is_flag=True, help="启动 HTTP 服务查看报告")
@click.option("--port", default=8080, help="HTTP 服务端口")
@click.pass_context
def report(ctx: click.Context, allure_dir: str | None, serve: bool, port: int) -> None:
    """查看测试报告"""
    import subprocess

    env = ctx.obj["env"]
    config = load_config(env)
    report_dir = allure_dir or config.report_allure_dir

    if not Path(report_dir).exists() or not any(Path(report_dir).iterdir()):
        console.print("[yellow]报告目录为空，请先运行测试并启用 --allure[/yellow]")
        return

    if serve:
        console.print(f"[bold]启动 Allure 报告服务: http://localhost:{port}[/bold]")
        cmd = ["allure", "serve", str(report_dir), "--port", str(port)]
        subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    else:
        console.print(f"[bold]生成 Allure HTML 报告...[/bold]")
        output_dir = str(Path(report_dir).parent / "html")
        cmd = ["allure", "generate", str(report_dir), "-o", output_dir, "--clean"]
        subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        console.print(f"[green]报告已生成: {output_dir}/index.html[/green]")


# ============================================================
# 工具函数
# ============================================================

def _get_llm_client(config, use_llm: bool, flag_name: str) -> LlmClient | None:
    """获取 LLM 客户端（检查配置和提示）"""
    if not use_llm:
        return None

    llm_config = build_llm_config(config)

    if not llm_config:
        console.print(
            f"[yellow]{flag_name} 已启用但未配置 LLM，请设置环境变量:[/yellow]\n"
            "  export LLM_BASE_URL=https://api.deepseek.com/v1\n"
            "  export LLM_API_KEY=your-api-key\n"
            "  export LLM_MODEL=deepseek-chat"
        )
        return None

    return LlmClient(llm_config)


if __name__ == "__main__":
    cli()
