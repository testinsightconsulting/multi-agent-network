# Project Structure

```
multi-agent-network/
├── main.py                      # Main entry point
├── pyproject.toml               # Project dependencies
├── README.md                    # Main documentation
├── QUICKSTART.md                # Quick start guide
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
│
├── config/                      # Configuration files
│   ├── topology.yaml            # Network topology definition
│   ├── router1.yaml             # Router 1 device config
│   ├── router2.yaml             # Router 2 device config
│   └── switch1.yaml             # Switch 1 device config
│
├── docs/                         # Documentation
│   └── TOPOLOGY_ORCHESTRATION.md # Orchestration topologies and inventory_id routing
│
├── examples/                     # Example configurations
│   └── sample_topology.yaml     # Example topology
│
├── knowledge_base/              # RAG knowledge base
│   ├── cisco/                   # Cisco documentation
│   ├── juniper/                 # Juniper documentation
│   └── generic/                 # Generic networking docs
│
└── src/                         # Source code
    ├── __init__.py
    │
    ├── agent/                   # Agent system
    │   ├── __init__.py
    │   ├── device_agent.py     # Core device agent
    │   ├── message_bus.py      # Inter-agent communication
    │   └── agent_registry.py   # Agent discovery (keyed by agent_id / inventory_id)
    │
    ├── topology/                # Orchestration topology loading
    │   ├── __init__.py
    │   └── topology_loader.py  # TOSCA/Spirent Velocity YAML, device discovery by inventory_id
    │
    ├── knowledge/               # Knowledge base system
    │   ├── __init__.py
    │   ├── rag_engine.py        # Local RAG system
    │   └── web_search.py       # Web search fallback
    │
    ├── device/                  # Device interfaces
    │   ├── __init__.py
    │   └── device_interface.py  # Device abstraction
    │
    ├── cli/                     # CLI interface
    │   ├── __init__.py
    │   └── agent_cli.py         # User interface
    │
    └── utils/                   # Utilities
        ├── __init__.py
        └── logger.py            # Logging utilities
```

## Key Components

### Agent System (`src/agent/`)
- **concierge_agent.py**: **Topology Concierge** – single entry point for users
  - User always talks to the Concierge; never directly to specialists
  - Tools: get_topology_overview, query_specialist(inventory_id, question), query_multiple_specialists
  - Redirects user questions to the right specialist agent(s) by inventory_id
  
- **device_agent.py**: Specialist agent representing a network device (used by Concierge, not by user directly)
  - Device-specific knowledge and capabilities
  - Tool definitions for Gemini function calling
  - Conversation management
  
- **message_bus.py**: Inter-agent communication system
  - Message routing between agents
  - Async message handling
  - Response waiting mechanism
  
- **agent_registry.py**: Agent discovery and management
  - Agent registration (by agent_id; for orchestration topologies, agent_id = inventory_id UUID)
  - Capability lookup
  - Topology information

### Topology (`src/topology/`)
- **topology_loader.py**: Load TOSCA/Spirent Velocity orchestration topologies
  - Discovers devices from `node_templates` (com.spirent.velocity.Device)
  - Each device has **inventory_id** (UUID) → specialist agent for that device
  - Builds DeviceContext from property_groups (ipAddress, Make, Model, OS Version, credentials)

### Knowledge System (`src/knowledge/`)
- **rag_engine.py**: Local RAG for device documentation
  - ChromaDB integration
  - Device-specific collections
  - Fallback file search
  
- **web_search.py**: Internet search fallback
  - Serper API support
  - Tavily API support
  - Gemini web search integration

### Device Interface (`src/device/`)
- **device_interface.py**: Device abstraction layer
  - Abstract base class
  - Simulated device implementation
  - Ready for SSH/API implementations

### CLI (`src/cli/`)
- **agent_cli.py**: User interface
  - Agent selection
  - Conversation management
  - Agent switching
  - Topology loading

## Configuration Files

### topology.yaml
Defines the network topology and agent configurations:
- Agent IDs and names
- Device types, models, OS versions
- Management IPs
- Device-specific commands
- Knowledge base paths

### Device Config Files (router1.yaml, etc.)
Simulated device configurations:
- BGP configuration
- OSPF settings
- Interface configurations
- VLANs, STP, etc.

## Data Flow

1. **User Input** → CLI
2. **CLI** → Selected Agent
3. **Agent** → Gemini API (with tools)
4. **Tools** → Device Interface / Other Agents / Knowledge Base
5. **Response** → User

## Inter-Agent Communication Flow

1. Agent A calls `query_other_agent` tool
2. Tool creates `AgentMessage`
3. Message sent via `MessageBus`
4. MessageBus routes to Agent B
5. Agent B processes query using its tools
6. Agent B sends response back
7. Response returned to Agent A
8. Agent A includes response in its answer

