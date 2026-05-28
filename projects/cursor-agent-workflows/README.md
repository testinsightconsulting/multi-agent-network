# Cursor Agent Workflows

Starter kit for Cursor IDE agent projects: shared skills, deployment guard hooks, and `AGENTS.md` conventions. Complements the public [claude-nexus](https://github.com/intisanchez/claude-nexus) hub used for Claude Code.

## What is included

| Path | Purpose |
|------|---------|
| `templates/.cursor/rules/` | Persistent agent guidance |
| `templates/.cursor/skills/git-manager/` | Git/GitHub operations skill |
| `templates/AGENTS.md` | Project agent instructions |
| `templates/hooks/prevent-deploy.sh` | Blocks direct infra commands from subagents |
| `examples/minimal-lab-project/` | Copy-paste scaffold for a new lab repo |

## Quick start

```bash
cp -r templates/.cursor your-project/.cursor
cp templates/AGENTS.md your-project/
mkdir -p your-project/.cursor/hooks
cp templates/hooks/prevent-deploy.sh your-project/.cursor/hooks/
```

Register the hook in Cursor settings or `hooks.json` to run on agent shell commands.

## Related work

- [claude-nexus](https://github.com/intisanchez/claude-nexus) — master hub for Claude Code (skills library, MCP repository, sysadmin)
- [multi-agent-network](../..) — multi-agent lab portfolio (device mesh, topology orchestration, eval harness, NetBox MCP tools)
