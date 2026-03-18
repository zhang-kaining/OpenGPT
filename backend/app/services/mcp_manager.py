"""
MCP Manager
===========
读取 backend/mcp.json，通过 langchain-mcp-adapters 连接 MCP Server，
将所有 MCP 工具转换为 OpenAI Function Calling 格式。

mcp.json 格式（与 Cursor 完全一致）：
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "my-server": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": { "MY_KEY": "value" }
    }
  }
}

依赖：pip install langchain-mcp-adapters
若未安装或 mcp.json 不存在，则静默降级（不影响其他功能）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MCP_CONFIG_PATH = Path(__file__).parent.parent.parent / "mcp.json"

# MCP 工具的调用函数类型：async (tool_name, args) -> str
McpCallable = Any


class McpManager:
    def __init__(self) -> None:
        self._tool_definitions: list[dict] = []
        self._tool_map: dict[str, McpCallable] = {}  # tool_name -> langchain Tool
        self._available = False

    async def load(self, config_path: Path = MCP_CONFIG_PATH) -> None:
        """读取 mcp.json，连接所有 MCP Server，加载工具列表"""
        if not config_path.exists():
            logger.info("mcp.json 不存在，MCP 功能未启用")
            return

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            logger.warning("langchain-mcp-adapters 未安装，MCP 功能不可用。运行: pip install langchain-mcp-adapters")
            return

        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("mcp.json 解析失败: %s", e)
            return

        servers: dict = config.get("mcpServers", {})
        if not servers:
            logger.info("mcp.json 中没有配置任何 MCP Server")
            return

        # 转换为 langchain-mcp-adapters 格式
        client_config: dict[str, dict] = {}
        for server_name, server_cfg in servers.items():
            transport = server_cfg.get("type") or server_cfg.get("transport", "stdio")
            entry: dict[str, Any] = {}

            if transport in ("sse",):
                # SSE 传输：langchain-mcp-adapters 用 "sse" transport
                entry["transport"] = "sse"
                entry["url"] = server_cfg["url"]
                if "headers" in server_cfg:
                    entry["headers"] = server_cfg["headers"]
            elif transport in ("http", "streamable-http", "streamable_http"):
                entry["transport"] = "streamable_http"
                entry["url"] = server_cfg["url"]
                if "headers" in server_cfg:
                    entry["headers"] = server_cfg["headers"]
            else:
                # stdio（默认）
                entry["transport"] = "stdio"
                if "command" in server_cfg:
                    entry["command"] = server_cfg["command"]
                if "args" in server_cfg:
                    entry["args"] = server_cfg["args"]
                if "env" in server_cfg:
                    entry["env"] = server_cfg["env"]

            client_config[server_name] = entry

        try:
            client = MultiServerMCPClient(client_config)
            lc_tools = await client.get_tools()
        except Exception as e:
            logger.error("MCP 工具加载失败: %s", e)
            return

        for lc_tool in lc_tools:
            tool_name = lc_tool.name
            # 转换为 OpenAI Function Calling 格式
            definition = _lc_tool_to_openai_definition(lc_tool)
            self._tool_definitions.append(definition)
            self._tool_map[tool_name] = lc_tool

        self._available = True
        logger.info("MCP 工具加载完成: %d 个工具 from %d 个 Server",
                    len(self._tool_definitions), len(servers))

    @property
    def available(self) -> bool:
        return self._available

    @property
    def tool_definitions(self) -> list[dict]:
        return self._tool_definitions

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._tool_map

    async def call_tool(self, tool_name: str, args: dict) -> str:
        """调用 MCP 工具，返回字符串结果"""
        lc_tool = self._tool_map.get(tool_name)
        if not lc_tool:
            return f"MCP 工具 '{tool_name}' 不存在"
        try:
            result = await lc_tool.ainvoke(args)
            return str(result)
        except Exception as e:
            logger.error("MCP 工具调用失败 [%s]: %s", tool_name, e)
            return f"工具执行失败: {e}"


def _lc_tool_to_openai_definition(lc_tool: Any) -> dict:
    """将 LangChain Tool 转换为 OpenAI Function Calling 格式"""
    # LangChain MCP Tool 已经有 args_schema（Pydantic model）
    try:
        schema = lc_tool.args_schema.model_json_schema() if lc_tool.args_schema else {}
        # 清理 Pydantic 特有字段
        schema.pop("title", None)
        properties = schema.get("properties", {})
        for prop in properties.values():
            prop.pop("title", None)
        parameters = {
            "type": "object",
            "properties": properties,
            "required": schema.get("required", []),
        }
    except Exception:
        parameters = {"type": "object", "properties": {}}

    return {
        "type": "function",
        "function": {
            "name": lc_tool.name,
            "description": lc_tool.description or lc_tool.name,
            "parameters": parameters,
        },
    }


# ---------- 全局单例 ----------

_manager: McpManager | None = None


def get_mcp_manager() -> McpManager:
    global _manager
    if _manager is None:
        _manager = McpManager()
    return _manager
