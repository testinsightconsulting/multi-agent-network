# GitHub Actions CI

The CI workflow lives at [docs/github-actions-ci.yml](github-actions-ci.yml) until your GitHub PAT can push files under `.github/workflows/`.

## Why

GitHub rejects pushes that create or update workflow files unless the token has the **`workflow`** scope (classic PAT) or **Actions: Read and write** (fine-grained PAT).

## Enable CI on the repo

1. Create or edit a PAT at https://github.com/settings/tokens
   - Classic: enable scope **`workflow`** (and **`repo`** for private repos)
   - Fine-grained: Repository access to `testinsightconsulting/multi-agent-network`, permission **Actions: Read and write**
2. Update your credential (Git Credential Manager or `gh auth login --with-token`).
3. Install the workflow:

```powershell
cd D:\Projects\multi-agent-network
New-Item -ItemType Directory -Force -Path .github\workflows
Copy-Item docs\github-actions-ci.yml .github\workflows\ci.yml
git add .github/workflows/ci.yml
git commit -m "Enable GitHub Actions CI for all projects"
git push origin main
```

After a successful push, Actions runs on each push/PR to `main`.
