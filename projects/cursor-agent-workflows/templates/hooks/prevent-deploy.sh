#!/usr/bin/env bash
# Deployment guard: block direct infrastructure commands from agent shells.
set -euo pipefail

CMD="${1:-}"
BLOCKED_PATTERN='(ssh |scp |rsync .*@|terraform apply|terraform destroy|kubectl apply|docker compose up|ansible-playbook|systemctl )'

if echo "$CMD" | grep -Eiq "$BLOCKED_PATTERN"; then
  echo "BLOCKED: Direct infrastructure actions must go through the hub sysadmin process."
  exit 2
fi

exit 0
