# API Test Framework

AI + 接口自动化测试框架：支持接口文档解析、AI 测试用例生成、自动执行、报告输出。

## 快速开始

```bash
# 安装依赖
pip install -e ".[dev]"

# 配置 AI（可选，用于智能解析和用例生成）
export LLM_BASE_URL=https://api.deepseek.com/v1
export LLM_API_KEY=your-api-key
export LLM_MODEL=deepseek-chat

# 解析接口文档
api-test parse data/api_docs/swagger_sample.json --llm

# 生成测试用例
api-test generate data/api_docs/ --llm

# 执行测试
api-test run output/testcases/ --env dev

# 查看报告
api-test report
```

## 功能特性

- **多格式文档解析**：OpenAPI / Apifox / Markdown / AI 自然语言
- **AI 测试用例生成**：DeepSeek 驱动，正向/逆向/边界全覆盖
- **接口依赖管理**：自动 Token 维护，接口间参数传递
- **智能断言**：状态码、JSON Schema、响应时间、字段断言
- **数据驱动**：CSV / JSON / YAML 参数化
- **Allure 报告**：请求/响应详情、失败 cURL 复现

## CLI 命令

| 命令 | 说明 |
|------|------|
| `api-test parse <doc>` | 解析接口文档，输出结构化接口列表 |
| `api-test generate <dir>` | 生成 pytest 测试用例 |
| `api-test run [dir]` | 执行测试 |
| `api-test report` | 查看 Allure 报告 |
