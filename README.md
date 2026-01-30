# Multi-Agent Network Device Management System

A distributed AI-powered network management system where each network device is represented by an expert agent that can communicate with other agents. Each agent understands its device-specific configuration, can query documentation via RAG or web search, and can collaborate with other agents to solve network-wide problems.

## Features

- **Multi-Agent Architecture**: Each network device has its own expert AI agent
- **Inter-Agent Communication**: Agents can query each other for information
- **Device-Specific Expertise**: Each agent understands its device type, model, and OS version
- **RAG + Web Search**: Local knowledge base with internet fallback for documentation
- **Flexible Entry Point**: Start conversations with any agent
- **Context Preservation**: Conversations maintain context across agent interactions

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Agent 1    │◄────►│ Message Bus │◄────►│  Agent 2    │
│ (Router 1)  │      │             │      │ (Router 2)  │
└─────────────┘      └─────────────┘      └─────────────┘
      │                     │                     │
      │                     │                     │
      └─────────────────────┴─────────────────────┘
                            │
                    ┌───────┴────────┐
                    │  Agent 3      │
                    │  (Switch 1)   │
                    └───────────────┘
```

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager (or pip)
- Gemini API key

## Installation

1. Clone or navigate to the project directory:
```bash
cd multi-agent-network
```

2. Install dependencies:
```bash
uv sync
# or
pip install -e .
```

3. Create a `.env` file with your Gemini API key:
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Configuration

1. **Topology Configuration**: Edit `config/topology.yaml` to define your network devices:
```yaml
topology:
  name: "My Network"
  agents:
    - agent_id: "router1"
      device_name: "Core-Router-01"
      device_type: "cisco"
      model: "ASR1000"
      os_version: "IOS XE 16.09"
      management_ip: "192.168.1.1"
      commands:
        show_config: "show running-config"
        show_bgp: "show ip bgp"
```

2. **Device Configuration**: Create device-specific config files in `config/`:
   - `config/router1.yaml`
   - `config/router2.yaml`
   - `config/switch1.yaml`

3. **Knowledge Base** (Optional): Add device documentation to:
   - `knowledge_base/cisco/` - Cisco documentation
   - `knowledge_base/juniper/` - Juniper documentation
   - `knowledge_base/generic/` - Generic networking docs

## Usage

### Start the Multi-Agent System

```bash
uv run python -m src.cli.agent_cli --topology config/topology.yaml --agent router1
```

### Example Conversations

```
[Core-Router-01]> What's my BGP configuration?
# Agent reads and analyzes its configuration

[Core-Router-01]> Is router2's BGP configuration compatible with mine?
# Agent queries router2 agent via message bus

[Core-Router-01]> /switch router2
[Edge-Router-02]> What routes am I advertising?
# Switched to different agent

[Edge-Router-02]> Ask router1 if it can see my routes
# Agent queries router1 agent
```

### CLI Commands

- Type your question to interact with the current agent
- `/switch <agent_id>` - Switch to a different agent
- `/list` - List all available agents
- `exit` or `quit` - Exit the system

## How It Works

### Agent Capabilities

Each device agent can:
1. **Read Configuration**: Execute device-specific commands to read current state
2. **Analyze Configuration**: Compare against best practices using RAG
3. **Validate Features**: Check if features are correctly configured
4. **Query Other Agents**: Ask questions to other device agents
5. **Search Documentation**: Use local RAG or web search for device-specific info

### Inter-Agent Communication

Agents communicate through a message bus:
- Agent A can query Agent B using the `query_other_agent` tool
- Messages are routed automatically
- Responses maintain conversation context

### Knowledge Base

- **Local RAG**: Uses ChromaDB to index device documentation
- **Web Search**: Falls back to internet search when local knowledge is insufficient
- **Device-Specific**: Each agent queries knowledge relevant to its device type

## Project Structure

```
multi-agent-network/
├── src/
│   ├── agent/
│   │   ├── device_agent.py      # Core device agent
│   │   ├── message_bus.py       # Inter-agent communication
│   │   └── agent_registry.py    # Agent discovery
│   ├── knowledge/
│   │   ├── rag_engine.py        # Local RAG system
│   │   └── web_search.py       # Web search fallback
│   ├── device/
│   │   └── device_interface.py  # Device abstraction
│   └── cli/
│       └── agent_cli.py         # User interface
├── config/
│   ├── topology.yaml            # Network topology
│   └── *.yaml                   # Device configurations
├── knowledge_base/
│   ├── cisco/                   # Cisco documentation
│   ├── juniper/                 # Juniper documentation
│   └── generic/                 # Generic networking docs
└── pyproject.toml
```

## Extending the System

### Adding a New Device Type

1. Add device to `config/topology.yaml`
2. Create device config file in `config/`
3. Optionally add documentation to `knowledge_base/`

### Implementing Real Device Communication

Replace `SimulatedDevice` in `src/device/device_interface.py` with real SSH/API implementations:
- SSH-based (paramiko, netmiko)
- REST API (httpx, requests)
- NETCONF/YANG

### Adding New Agent Capabilities

Extend `DeviceAgent._create_tools()` to add new tools that agents can use.

## Limitations

- Currently uses simulated devices (PoC)
- RAG requires ChromaDB setup for full functionality
- Web search requires API keys for external services

## Future Enhancements

- Real device connectivity (SSH, NETCONF, REST API)
- Configuration change management
- Network-wide analysis and recommendations
- Event-driven agent collaboration
- Persistent conversation storage
- Multi-user support

## License

See LICENSE file for details.

## Contributing

This is a proof of concept. Contributions welcome!

