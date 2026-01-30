# Orchestration Topology and Concierge Routing

## Overview

**Users never talk directly to specialist agents.** They always talk to the **Topology Concierge**. The Concierge discovers devices from the loaded topology and **redirects** user questions to the appropriate specialist agent(s) by **inventory_id** (or agent_id).

The system can load **orchestration topologies** (TOSCA / Spirent Velocity YAML). In these topologies:

1. **Devices** are defined in `topology_template.node_templates` with type `com.spirent.velocity.Device`.
2. Each device has an **`inventory_id`** (a UUID) that uniquely identifies it in the inventory.
3. The **specialist agent** for that device is identified by this **`inventory_id`**: one agent per device, responsible for diagnosis, configuration management, and device-specific advice.
4. The **Concierge Agent** is the single entry point: it knows the topology (devices and their IDs) and routes user questions to the right specialist(s).

## Topology Format (TOSCA / Spirent Velocity)

Example structure (e.g. `Zero_Touch_Lab_Orchestration_Topology.yaml`):

```yaml
tosca_definitions_version: tosca_simple_yaml_1_0
topology_template:
  node_templates:
    device_ic05c0493-11b0-4b72-8b00-658dd2142abb:
      type: com.spirent.velocity.Device
      properties:
        id: ic05c0493-11b0-4b72-8b00-658dd2142abb
        name: Arista DUT
        inventory_id: abc67f38-8b7e-4bf0-8aa4-8d2cbcc8a0b6   # ← Specialist agent ID (UUID)
        inventory_name: Arista DUT
        property_groups:
          - name: System Identification
            group:
              - name: ipAddress
                value: 192.168.168.3
              - name: Hostname
                value: Arista-DUT
              - name: Make
                value: Arista
              - name: Model
                value: DCS-7048T-A-R
              - name: OS Version
                value: 4.15.10M
          - name: Credentials
            group:
              - name: username
                value: admin
              - name: password
                value: Apnt123!
```

- **`inventory_id`** (e.g. `abc67f38-8b7e-4bf0-8aa4-8d2cbcc8a0b6`) is the UUID of the specialist agent for this device.
- Device metadata (IP, hostname, Make, Model, OS Version, credentials) is read from `property_groups` and used to build the device context and config.

## Flow

1. **Load topology**  
   User passes a topology file path (e.g. `Zero_Touch_Lab_Orchestration_Topology.yaml`).

2. **Discover devices**  
   The topology loader parses `topology_template.node_templates`, finds all `com.spirent.velocity.Device` nodes, and extracts for each:
   - `inventory_id` (UUID) → **specialist agent identifier**
   - `inventory_name`, Hostname, Make, Model, OS Version, ipAddress, credentials

3. **Create specialist agents**  
   For each device, a **DeviceAgent** (specialist) is created and registered with **agent_id = inventory_id**. These agents are **not** directly exposed to the user.

4. **Create the Concierge**  
   The **Concierge Agent** is created with an overview of the topology (list of devices and their IDs). The user interface connects **only** to the Concierge.

5. **User talks to the Concierge; Concierge redirects to specialists**  
   - User asks a question (e.g. “What is the BGP config on the Arista?” or “List all devices”).
   - Concierge uses **get_topology_overview** to see devices and their IDs.
   - Concierge uses **query_specialist(agent_id, question)** to send the question to the right specialist(s) (by inventory_id).
   - Concierge synthesizes specialist responses and answers the user. The user never talks to a specialist directly.

## Running with an Orchestration Topology

```bash
# Load topology; you talk to the Concierge (no --agent option)
uv run python main.py --topology "C:\Users\Inti\Downloads\Zero_Touch_Lab_Orchestration_Topology.yaml"
```

In the CLI you always see **`[Concierge]>`**. Ask in natural language; the Concierge will route to the right specialist(s):

- “List all devices in the topology”
- “What is the configuration of the Arista DUT?”
- “Ask the specialist for device abc67f38-8b7e-4bf0-8aa4-8d2cbcc8a0b6 about its BGP config”

- **`/list`** – Shortcut to list devices and their **inventory_id** (Concierge uses these IDs to route).

## Code Locations

| Component | Location | Role |
|-----------|----------|------|
| **Concierge Agent** | `src/agent/concierge_agent.py` | Single entry point; user talks only to Concierge. Tools: `get_topology_overview`, `query_specialist(inventory_id, question)`, `query_multiple_specialists`. |
| Topology loader | `src/topology/topology_loader.py` | Parses TOSCA/Spirent YAML, returns `Topology` with `DeviceNode` (each has `inventory_id`). |
| Orchestration detection | `is_orchestration_topology()` | Detects if YAML is orchestration format (node_templates with velocity types). |
| Agent creation from topology | `src/cli/agent_cli.py` | Creates specialist DeviceAgents (agent_id = inventory_id), then creates Concierge with topology overview; chat loop is Concierge-only. |
| Agent registry | `src/agent/agent_registry.py` | Specialists registered by **inventory_id**; Concierge looks them up to route queries. |

## Summary

- **Users always talk to the Topology Concierge**; they never talk directly to specialist agents.
- The Concierge **discovers** devices from the topology and **redirects** user questions to the right specialist(s) by **inventory_id**.
- **Specialist agents** (one per device, keyed by inventory_id) handle diagnosis, configuration management, and device-specific advice; the Concierge synthesizes their responses for the user.
