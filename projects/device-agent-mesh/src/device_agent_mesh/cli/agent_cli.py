"""CLI interface for multi-agent network system. User always talks to the Concierge; Concierge routes to specialist agents."""
import click
import asyncio
import nest_asyncio
import os
import getpass
from pathlib import Path
import yaml
from typing import Dict, List, Tuple
from dotenv import load_dotenv

from device_agent_mesh.agent.device_agent import DeviceAgent, DeviceContext
from device_agent_mesh.agent.concierge_agent import ConciergeAgent, TopologyOverview, SpecialistInfo
from device_agent_mesh.agent.message_bus import MessageBus
from device_agent_mesh.agent.agent_registry import AgentRegistry
from device_agent_mesh.device.device_interface import SimulatedDevice
from device_agent_mesh.device.ssh_device import GenericSshDeviceInterface
from device_agent_mesh.knowledge.rag_engine import RAGEngine
from device_agent_mesh.knowledge.web_search import WebSearch
from topology_orchestration.topology_loader import (
    load_topology,
    is_orchestration_topology,
    get_knowledge_base_path_for_make,
)
from device_agent_mesh.device.command_catalog import (
    get_commands_for_device,
    get_session_prep_for_device,
    get_enable_command_for_device,
    resolve_vendor_key,
    resolve_vendor_from_metadata,
)
from device_agent_mesh.device.prompt_catalog import get_prompt_handlers_for_device, get_prompt_regex_for_device

# Load environment variables
load_dotenv()


def _create_agents_from_simple_topology(topology_config: dict, message_bus, agent_registry, rag_engine, web_search, api_key: str) -> Dict[str, DeviceAgent]:
    """Create DeviceAgents from simple topology.yaml (topology.agents)."""
    agents: Dict[str, DeviceAgent] = {}
    for agent_config in topology_config["topology"]["agents"]:
        context = DeviceContext(
            agent_id=agent_config["agent_id"],
            device_name=agent_config["device_name"],
            device_type=resolve_vendor_from_metadata([agent_config.get("device"), agent_config.get("device_type"), agent_config.get("device_name")]),
            model=agent_config.get("model", ""),
            os_version=agent_config.get("os_version", ""),
            management_ip=agent_config["management_ip"],
            commands=agent_config["commands"],
            knowledge_base_path=agent_config["knowledge_base_path"]
        )
        device_config_file = Path(f"config/{agent_config['agent_id']}.yaml")
        if not device_config_file.exists():
            default_config = {
                "device": agent_config["device_name"],
                "bgp": {
                    "asn": 65000 + int(agent_config["agent_id"][-1]) if agent_config["agent_id"][-1].isdigit() else 65001,
                    "router_id": agent_config["management_ip"],
                    "neighbors": []
                },
                "interfaces": {
                    "GigabitEthernet0/0": {"ip": agent_config["management_ip"], "status": "up"},
                    "GigabitEthernet0/1": {"ip": "10.0.0.1", "status": "up"}
                }
            }
            device_config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(device_config_file, 'w') as f:
                yaml.dump(default_config, f)
        # Support real SSH connections if enabled
        use_ssh = os.environ.get("SSH_ENABLED", "true").strip().lower() in ("1", "true", "yes")
        
        if use_ssh and context.management_ip and context.management_ip != "0.0.0.0":
            # In a real app, we might prompt for creds per device or use a common one
            # For simple topology, we'll try to use env vars or prompt once
            username = os.environ.get("SSH_USERNAME") or "admin"
            password = os.environ.get("SSH_PASSWORD") or "admin"
            
            device_interface = GenericSshDeviceInterface(
                host=context.management_ip,
                username=username,
                password=password,
                enable_password=None, # explicit enable pass not handled in simple topo for now
                session_prep_commands=get_session_prep_for_device(context.device_type),
                prompt_regex=get_prompt_regex_for_device(context.device_type),
                prompt_handlers=get_prompt_handlers_for_device(context.device_type),
            )
        else:
            device_interface = SimulatedDevice(
                device_name=agent_config["device_name"],
                config_file=str(device_config_file)
            )
            
        agent = DeviceAgent(
            context=context,
            gemini_api_key=api_key,
            message_bus=message_bus,
            agent_registry=agent_registry,
            device_interface=device_interface,
            rag_engine=rag_engine,
            web_search=web_search
        )
        agents[agent_config["agent_id"]] = agent
    return agents


def _create_agents_from_orchestration_topology(topology_path: Path, message_bus, agent_registry, rag_engine, web_search, api_key: str) -> Dict[str, DeviceAgent]:
    """Create DeviceAgents from TOSCA/Spirent Velocity topology. Each device's specialist agent is keyed by inventory_id (UUID)."""
    topo = load_topology(str(topology_path))
    agents: Dict[str, DeviceAgent] = {}
    config_dir = Path("config")
    config_dir.mkdir(parents=True, exist_ok=True)
    credentials_by_type = {}
    creds_file = Path(".credentials.yaml")
    if creds_file.exists():
        try:
            with open(creds_file, "r") as f:
                credentials_by_type = yaml.safe_load(f) or {}
        except Exception as e:
            click.echo(f"Warning: Could not load {creds_file}: {e}")
    
    use_ssh = os.environ.get("SSH_ENABLED", "true").strip().lower() in ("1", "true", "yes")
    for device in topo.devices:
        # Specialist agent for this device is identified by inventory_id
        agent_id = device.inventory_id
        device_type = resolve_vendor_from_metadata([device.device, device.make, device.inventory_name])
        context = DeviceContext(
            agent_id=agent_id,
            device_name=device.inventory_name or device.hostname or agent_id,
            device_type=device_type,
            model=device.model or "",
            os_version=device.os_version or "",
            management_ip=device.ip_address or "",
            commands=get_commands_for_device(device_type=device_type, model=device.model or ""),
            knowledge_base_path=get_knowledge_base_path_for_make(device_type),
        )
        # Config file keyed by inventory_id so it's stable
        device_config_file = config_dir / f"{agent_id}.yaml"
        if not device_config_file.exists():
            default_config = {
                "device": context.device_name,
                "management_ip": device.ip_address,
                "hostname": device.hostname,
                "make": device.make,
                "model": device.model,
                "os_version": device.os_version,
                "interfaces": {},
            }
            with open(device_config_file, 'w') as f:
                yaml.dump(default_config, f)
        # Generic SSH specialist: prompt for credentials (per vendor) and use SSH interface
        if use_ssh and context.management_ip:
            dtype = context.device_type or "generic"
            if dtype not in credentials_by_type:
                click.echo(f"\nSSH credentials required for {context.device_name} ({context.management_ip}) [{dtype}]")
                username = input(f"{dtype} SSH username: ").strip()
                password = getpass.getpass(f"{dtype} SSH password: ").strip()
                enable_password = getpass.getpass(f"{dtype} enable password (optional): ").strip()
                if not username or not password:
                    raise ValueError("SSH credentials are required to proceed.")
                credentials_by_type[dtype] = {
                    "username": username,
                    "password": password,
                    "enable_password": enable_password or None
                }
                # Save credentials to file
                try:
                    with open(creds_file, "w") as f:
                        yaml.dump(credentials_by_type, f)
                except Exception as e:
                    click.echo(f"Warning: Could not save credentials to {creds_file}: {e}")

            creds = credentials_by_type[dtype]
            device_interface = GenericSshDeviceInterface(
                host=context.management_ip,
                username=creds["username"],
                password=creds["password"],
                enable_password=creds["enable_password"],
                enable_command=get_enable_command_for_device(dtype) or None,
                session_prep_commands=get_session_prep_for_device(dtype),
                prompt_regex=get_prompt_regex_for_device(dtype),
                prompt_handlers=get_prompt_handlers_for_device(dtype),
                config_command=context.commands.get("show_config", "show running-config"),
            )
        else:
            device_interface = SimulatedDevice(
                device_name=context.device_name,
                config_file=str(device_config_file)
            )
        agent = DeviceAgent(
            context=context,
            gemini_api_key=api_key,
            message_bus=message_bus,
            agent_registry=agent_registry,
            device_interface=device_interface,
            rag_engine=rag_engine,
            web_search=web_search
        )
        agents[agent_id] = agent
    return agents


def _build_topology_overview(
    specialists: Dict[str, DeviceAgent],
    topology_name: str,
) -> TopologyOverview:
    """Build topology overview for the concierge (devices only, no concierge)."""
    specialists_list = [
        SpecialistInfo(
            id=aid,
            name=a.context.device_name,
            type=a.context.device_type,
            ip=a.context.management_ip or "",
            model=a.context.model or "",
        )
        for aid, a in specialists.items()
    ]
    return TopologyOverview(name=topology_name, specialists=specialists_list)


@click.command()
@click.option("--topology", default="config/topology.yaml", help="Topology file (simple YAML or TOSCA/Spirent Velocity)")
@click.option("--api-key", envvar="GEMINI_API_KEY", help="Gemini API Key")
def main(topology: str, api_key: str):
    """Multi-Agent Network CLI. You always talk to the Concierge; it discovers devices and redirects questions to specialist agents."""
    
    if not api_key:
        click.echo("Error: GEMINI_API_KEY not found. Set it in .env or pass --api-key.")
        return
    
    topology_path = Path(topology)
    if not topology_path.exists():
        click.echo(f"Error: Topology file not found: {topology}")
        return
    
    with open(topology_path, 'r') as f:
        raw_topology = yaml.safe_load(f)
    
    message_bus = MessageBus()
    agent_registry = AgentRegistry()
    rag_engine = RAGEngine()
    web_search = WebSearch()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Allow nested run_until_complete so Concierge→Specialist tool call can wait for response (avoids deadlock)
    nest_asyncio.apply(loop)
    loop.run_until_complete(message_bus.start())
    
    # Create specialist agents (devices); user never talks to them directly
    if is_orchestration_topology(raw_topology):
        specialists = _create_agents_from_orchestration_topology(
            topology_path, message_bus, agent_registry, rag_engine, web_search, api_key
        )
        topo = load_topology(str(topology_path))
        topology_name = topo.name
        click.echo(f"Loaded orchestration topology: {topo.name}")
        click.echo(f"Discovered {len(specialists)} device(s); specialist agents identified by inventory_id (UUID).")
    else:
        specialists = _create_agents_from_simple_topology(
            raw_topology, message_bus, agent_registry, rag_engine, web_search, api_key
        )
        topology_name = raw_topology.get("topology", {}).get("name", "Network Topology")
    
    # Concierge knows the topology and routes user questions to specialists
    topology_overview = _build_topology_overview(specialists, topology_name)
    concierge = ConciergeAgent(
        topology_overview=topology_overview,
        gemini_api_key=api_key,
        message_bus=message_bus,
        agent_registry=agent_registry,
    )
    
    click.echo("\n=== Multi-Agent Network (Concierge) ===")
    click.echo("You are talking to the Topology Concierge. Ask about devices, config, or diagnostics; the Concierge will route to the right specialist(s).")
    click.echo("Type 'exit' or 'quit' to leave. Use /list to see devices in the topology.\n")
    
    from datetime import datetime
    conversation_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    while True:
        try:
            user_input = input("[Concierge]> ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                break
            
            if user_input.startswith("/list"):
                click.echo("\nDevices in topology (Concierge routes to these by ID):")
                for s in topology_overview.specialists:
                    click.echo(f"  - {s.id}: {s.name} ({s.type}) {s.ip and f' @ {s.ip}' or ''}")
                click.echo()
                continue
            
            response = loop.run_until_complete(concierge.chat(user_input, conversation_id))
            click.echo(f"\n{response}\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            click.echo(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

