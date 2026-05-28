# Cursor Portfolio Map

This document explains how each public project in the monorepo reflects long-running Cursor agent work (without proprietary customer data).

| Project | Cursor workstream | What shipped publicly |
|---------|-------------------|------------------------|
| **device-agent-mesh** | Multi-agent network PoC with Gemini function calling, Concierge routing, inter-agent message bus | Runnable Python package with mock and SSH device backends |
| **topology-orchestration** | Velocity / TOSCA lab YAML integration, `inventory_id` as agent key | Standalone parser + sanitized example topologies |
| **agent-doc-evaluator** | Benchmarking agent answers on vendor documentation (evaluation-suite) | Deterministic rubric scorer + sample eval suite JSON |
| **netbox-lab-mcp-tools** | NetBox topology plugin MCP tools (reservations, resolution) | Reference MCP server with in-memory mock NetBox |
| **cursor-agent-workflows** | Hub skills, deployment guard, git-manager patterns | Cursor IDE template tree + minimal lab scaffold |

## Practices used across projects

- **Concierge pattern** — users never talk to specialist agents directly.
- **Verification before completion** — pytest harnesses per project.
- **Secret hygiene** — `.env` and lab credential YAML excluded from git.
- **Hub separation** — infrastructure deployments via claude-nexus sysadmin, not subagents.

## Not included (proprietary or sensitive)

- Customer-specific NetBox seed data and Groundworx deployments
- Full Auto-Tier-1 MVP connector certificates and production configs
- Raw Cursor chat exports (`cursor_*.md`)
- Live lab inventory UUID config files

## Next steps for contributors

1. Pick a project under `projects/` and run `uv sync && uv run pytest`.
2. Copy `cursor-agent-workflows/templates` into new lab repos.
3. Wire `netbox-lab-mcp` in Cursor MCP settings for agent-driven lab workflows.
