"""Stdio MCP server exposing NetBox lab reference tools."""
from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from netbox_lab_mcp import tools

app = Server("netbox-lab-mcp-tools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_topology",
            description="Create a draft lab topology in the mock NetBox store.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "site": {"type": "string"},
                    "slug": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "site"],
            },
        ),
        Tool(
            name="get_topology",
            description="Get a topology with nodes and links.",
            inputSchema={
                "type": "object",
                "properties": {"topology_id": {"type": "integer"}},
                "required": ["topology_id"],
            },
        ),
        Tool(
            name="list_topologies",
            description="List all topologies in the mock store.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="create_reservation",
            description="Create a reservation for a topology.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topology_id": {"type": "integer"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "owner_username": {"type": "string"},
                },
                "required": ["topology_id", "start", "end"],
            },
        ),
        Tool(
            name="resolve_topology",
            description="Mark a topology as resolved.",
            inputSchema={
                "type": "object",
                "properties": {"topology_id": {"type": "integer"}},
                "required": ["topology_id"],
            },
        ),
        Tool(
            name="release_topology",
            description="Release a topology back to draft.",
            inputSchema={
                "type": "object",
                "properties": {"topology_id": {"type": "integer"}},
                "required": ["topology_id"],
            },
        ),
        Tool(
            name="check_conflicts",
            description="Check reservation conflicts (mock always returns zero).",
            inputSchema={
                "type": "object",
                "properties": {"topology_id": {"type": "integer"}},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "create_topology": lambda args: tools.create_topology_tool(**args),
        "get_topology": lambda args: tools.get_topology_tool(**args),
        "list_topologies": lambda args: tools.list_topologies_tool(**args),
        "create_reservation": lambda args: tools.create_reservation_tool(**args),
        "resolve_topology": lambda args: tools.resolve_topology_tool(**args),
        "release_topology": lambda args: tools.release_topology_tool(**args),
        "check_conflicts": lambda args: tools.check_conflicts_tool(**args),
    }
    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"Unknown tool: {name}")
    result = handler(arguments or {})
    return [TextContent(type="text", text=str(result))]


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
