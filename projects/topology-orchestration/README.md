# Topology Orchestration

Parse Spirent Velocity / TOSCA orchestration topology YAML and expose devices by `inventory_id` for multi-agent lab systems.

## Install

```bash
cd projects/topology-orchestration
uv sync
```

## Inspect a topology

```bash
uv run topology-orchestration examples/zero_touch_lab.yaml
uv run topology-orchestration examples/layer3_crossover.yaml --json
```

## Library usage

```python
from topology_orchestration import load_topology

topo = load_topology("examples/zero_touch_lab.yaml")
for device in topo.devices:
    print(device.inventory_id, device.make, device.model)
```

See [docs/TOPOLOGY_ORCHESTRATION.md](docs/TOPOLOGY_ORCHESTRATION.md) for orchestration concepts.
