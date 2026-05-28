# NetBox Lab MCP Tools

Reference MCP tool implementations for NetBox lab topology, reservation, and resolution workflows. Uses an in-memory mock backend so agents and tests run without a live NetBox instance.

This is a **public companion** to full NetBox plugin work — it demonstrates MCP tool contracts built with Cursor, not proprietary customer deployments.

## Install

```bash
cd projects/netbox-lab-mcp-tools
uv sync
```

## Run MCP server (stdio)

```bash
uv run netbox-lab-mcp
```

Configure in Cursor MCP settings pointing at the command above.

## Tools

| Tool | Purpose |
|------|---------|
| `create_topology` | Create draft topology |
| `get_topology` | Fetch topology with nodes/links |
| `list_topologies` | List all topologies |
| `create_reservation` | Schedule lab reservation |
| `resolve_topology` | Mark topology resolved |
| `release_topology` | Return topology to draft |
| `check_conflicts` | Conflict check (mock returns zero) |

## Tests

```bash
uv run pytest
```
