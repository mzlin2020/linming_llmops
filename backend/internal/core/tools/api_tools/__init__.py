"""自定义 API 工具子系统：从 OpenAPI schema 动态生成可调用的外部工具。

- entities/  —— OpenAPISchema 解析 + ToolEntity
- providers/ —— ApiProviderManager（ToolEntity → LangChain StructuredTool）+ SSRF 安全封装
"""
