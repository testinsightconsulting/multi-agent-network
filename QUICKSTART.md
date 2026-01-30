# Quick Start Guide

## Setup (5 minutes)

1. **Install dependencies:**
```bash
cd multi-agent-network
uv sync
# or
pip install -e .
```

2. **Configure API key:**
```bash
cp .env.example .env
# Edit .env and add: GEMINI_API_KEY=your_key_here
```

3. **Verify configuration files exist:**
- `config/topology.yaml` ✓
- `config/router1.yaml` ✓
- `config/router2.yaml` ✓
- `config/switch1.yaml` ✓

## Run the System

You **always talk to the Concierge**; it discovers devices and redirects your questions to the right specialist(s). There is no direct specialist selection.

```bash
# Start with default topology (Concierge loads topology and specialists)
uv run python main.py

# Custom topology
uv run python main.py --topology examples/sample_topology.yaml

# Orchestration topology (TOSCA/Spirent Velocity): Concierge discovers devices by inventory_id
uv run python main.py --topology "path/to/Zero_Touch_Lab_Orchestration_Topology.yaml"
```

## Real SSH integration (prompted credentials)

If a device has a management IP and `SSH_ENABLED=true`, the CLI **prompts for SSH credentials** (per vendor/device type) before starting.
These credentials are used to establish a real SSH connection and run commands.

## Example Interactions

You always see **`[Concierge]>`**. The Concierge redirects your questions to the right specialist(s).

### Topology and device questions
```
[Concierge]> List all devices in the topology
[Concierge]> What is the BGP configuration on the Arista DUT?
[Concierge]> Show me interfaces for the device at 192.168.168.3
[Concierge]> /list
```

### Multi-device and analysis (Concierge routes to one or more specialists)
```
[Concierge]> Compare BGP config on all routers
[Concierge]> Validate the Arista DUT's BGP configuration
[Concierge]> Ask the device abc67f38-8b7e-4bf0-8aa4-8d2cbcc8a0b6 about its interfaces
```

See [docs/TOPOLOGY_ORCHESTRATION.md](docs/TOPOLOGY_ORCHESTRATION.md) for orchestration topologies and inventory_id routing.

## Troubleshooting

**Error: GEMINI_API_KEY not found**
- Make sure `.env` file exists and contains `GEMINI_API_KEY=your_key`

**Error: Topology file not found**
- Check that `config/topology.yaml` exists
- Or specify path with `--topology` option

**Agent not responding**
- Check that all device config files exist in `config/`
- Verify topology.yaml has correct agent IDs

**Inter-agent communication not working**
- Ensure message bus is running (should start automatically)
- Check that all agents are registered (use `/list` command)

## Next Steps

1. **Add real device connectivity**: Replace `SimulatedDevice` with SSH/API implementations
2. **Populate knowledge base**: Add device documentation to `knowledge_base/` directories
3. **Extend topology**: Add more devices to `config/topology.yaml`
4. **Customize agents**: Modify agent capabilities in `src/agent/device_agent.py`

