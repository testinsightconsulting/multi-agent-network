# Agent Instructions

You are working in a lab automation project managed with Cursor agent workflows.

## Rules

1. Never commit secrets (`.env`, credentials, API keys, tokens).
2. Never run direct deployment or SSH to production — request infrastructure changes through the hub sysadmin process.
3. Use the `git-manager` skill for all version control operations.
4. Prefer small, reviewable diffs; run tests before claiming work is complete.

## Project context

- Multi-agent device specialists live in `projects/device-agent-mesh`.
- Topology YAML uses Velocity/TOSCA orchestration format; load with `topology-orchestration`.
- NetBox lab MCP tools are reference implementations in `projects/netbox-lab-mcp-tools`.

## Verification

Before finishing a task:

- Run project tests (`uv run pytest`).
- Confirm no secrets in `git diff`.
- Update README if behavior or CLI changed.
