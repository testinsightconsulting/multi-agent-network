"""Load orchestration topologies (TOSCA / Spirent Velocity YAML)."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


# TOSCA / Spirent Velocity type names
TYPE_DEVICE = "com.spirent.velocity.Device"
TYPE_PORT = "com.spirent.velocity.Port"
TYPE_ETHERNET_LINK = "com.spirent.velocity.EthernetLink"


def _get_property_groups_map(node: Dict[str, Any]) -> Dict[str, str]:
    """Extract flat name -> value from property_groups (System Identification, Credentials, etc.)."""
    result: Dict[str, str] = {}
    for pg in node.get("property_groups", []) or []:
        for item in pg.get("group", []) or []:
            name = item.get("name")
            value = item.get("value")
            if name is not None and value is not None:
                result[name] = str(value)
    return result


def _get_requirement_target(node: Dict[str, Any], req_name: str) -> Optional[str]:
    """Get target node name from requirements (e.g. device, from, to)."""
    for req in node.get("requirements", []) or []:
        if isinstance(req, dict) and req_name in req:
            return req[req_name]
    return None


@dataclass
class DeviceNode:
    """A device in the topology (specialist agent identified by inventory_id)."""
    node_key: str  # topology node_templates key, e.g. device_ic05c0493-...
    inventory_id: str  # UUID - identifies the specialist agent for this device
    inventory_name: str
    make: str
    model: str
    hostname: str
    ip_address: str
    os_version: str
    device: str
    serial_number: str
    username: str
    password: str
    raw_properties: Dict[str, Any] = field(default_factory=dict)
    raw_property_groups: Dict[str, str] = field(default_factory=dict)

    @property
    def agent_id(self) -> str:
        """Specialist agent for this device is identified by inventory_id."""
        return self.inventory_id


@dataclass
class PortNode:
    """A port in the topology (optional, for topology graph)."""
    node_key: str
    inventory_id: str
    inventory_name: str
    device_node_key: Optional[str] = None  # from requirements.device


@dataclass
class EthernetLinkNode:
    """An ethernet link between two ports (optional)."""
    node_key: str
    name: str
    from_port_key: Optional[str] = None
    to_port_key: Optional[str] = None


@dataclass
class Topology:
    """Parsed orchestration topology (devices + optional ports/links)."""
    name: str
    devices: List[DeviceNode] = field(default_factory=list)
    ports: List[PortNode] = field(default_factory=list)
    links: List[EthernetLinkNode] = field(default_factory=list)
    raw_node_templates: Dict[str, Any] = field(default_factory=dict)

    def get_device_by_inventory_id(self, inventory_id: str) -> Optional[DeviceNode]:
        """Return the device whose specialist agent is identified by this inventory_id."""
        for d in self.devices:
            if d.inventory_id == inventory_id:
                return d
        return None

    def device_inventory_ids(self) -> List[str]:
        """List all inventory_id UUIDs (one per specialist agent)."""
        return [d.inventory_id for d in self.devices]


def is_orchestration_topology(data: Dict[str, Any]) -> bool:
    """Return True if this YAML is a TOSCA/orchestration topology (node_templates with velocity types)."""
    tt = data.get("topology_template") or {}
    node_templates = tt.get("node_templates") or {}
    for node in node_templates.values():
        if isinstance(node, dict):
            t = node.get("type", "")
            if TYPE_DEVICE in t or TYPE_PORT in t:
                return True
    return False


def load_topology(path: str) -> Topology:
    """
    Load a topology from YAML.
    Supports:
    - TOSCA / Spirent Velocity (topology_template.node_templates with com.spirent.velocity.Device/Port/EthernetLink).
    - Simple format (topology.agents) is NOT handled here; use existing config loader for that.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Topology file not found: {path}")

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not is_orchestration_topology(data):
        raise ValueError(
            "File is not a TOSCA/Spirent Velocity orchestration topology. "
            "Expected topology_template.node_templates with com.spirent.velocity.Device/Port."
        )

    tt = data.get("topology_template") or {}
    node_templates = tt.get("node_templates") or {}
    topology_name = "Orchestration Topology"
    if "topology" in node_templates:
        top_node = node_templates["topology"]
        if isinstance(top_node, dict):
            props = top_node.get("properties") or {}
            topology_name = props.get("name", topology_name)

    devices: List[DeviceNode] = []
    ports: List[PortNode] = []
    links: List[EthernetLinkNode] = []

    for node_key, node in node_templates.items():
        if not isinstance(node, dict):
            continue
        node_type = node.get("type", "")
        props = node.get("properties") or {}

        if node_type == TYPE_DEVICE:
            inv_id = props.get("inventory_id") or props.get("id") or ""
            inv_name = props.get("inventory_name") or props.get("name") or node_key
            pg_map = _get_property_groups_map(props)
            devices.append(
                DeviceNode(
                    node_key=node_key,
                    inventory_id=inv_id,
                    inventory_name=inv_name,
                    make=pg_map.get("Make", ""),
                    model=pg_map.get("Model", ""),
                    hostname=pg_map.get("Hostname", ""),
                    ip_address=pg_map.get("ipAddress", ""),
                    os_version=pg_map.get("OS Version", ""),
                    device=pg_map.get("Device", ""),
                    serial_number=pg_map.get("Serial Number", ""),
                    username=pg_map.get("username", ""),
                    password=pg_map.get("password", ""),
                    raw_properties=props,
                    raw_property_groups=pg_map,
                )
            )
        elif node_type == TYPE_PORT:
            inv_id = props.get("inventory_id") or props.get("id") or ""
            inv_name = props.get("inventory_name") or props.get("name") or node_key
            device_key = _get_requirement_target(node, "device")
            ports.append(
                PortNode(
                    node_key=node_key,
                    inventory_id=inv_id,
                    inventory_name=inv_name,
                    device_node_key=device_key,
                )
            )
        elif node_type == TYPE_ETHERNET_LINK:
            from_key = _get_requirement_target(node, "from")
            to_key = _get_requirement_target(node, "to")
            links.append(
                EthernetLinkNode(
                    node_key=node_key,
                    name=props.get("name", node_key),
                    from_port_key=from_key,
                    to_port_key=to_key,
                )
            )

    return Topology(
        name=topology_name,
        devices=devices,
        ports=ports,
        links=links,
        raw_node_templates=dict(node_templates),
    )


# Default commands and knowledge base by vendor (Make) for orchestration topologies
DEFAULT_COMMANDS_BY_MAKE: Dict[str, Dict[str, str]] = {
    "cisco": {
        "show_config": "show running-config",
        "show_bgp": "show ip bgp",
        "show_interfaces": "show ip interface brief",
        "show_ospf": "show ip ospf neighbor",
    },
    "juniper": {
        "show_config": "show configuration",
        "show_bgp": "show bgp summary",
        "show_interfaces": "show interfaces terse",
        "show_ospf": "show ospf neighbor",
    },
    "arista": {
        "show_config": "show running-config",
        "show_bgp": "show ip bgp summary",
        "show_interfaces": "show ip interface brief",
        "show_ospf": "show ip ospf neighbor",
    },
    "spirent": {
        "show_config": "show configuration",
        "show_interfaces": "show interfaces",
        "show_status": "show status",
    },
}

DEFAULT_KNOWLEDGE_BASE_BY_MAKE: Dict[str, str] = {
    "cisco": "knowledge_base/cisco",
    "juniper": "knowledge_base/juniper",
    "arista": "knowledge_base/generic",
    "spirent": "knowledge_base/generic",
    "vyos": "knowledge_base/generic",
}


def get_default_commands_for_make(make: str) -> Dict[str, str]:
    """Return default CLI commands for a vendor (Make)."""
    key = (make or "generic").strip().lower()
    return DEFAULT_COMMANDS_BY_MAKE.get(key, DEFAULT_COMMANDS_BY_MAKE.get("cisco", {})).copy()


def get_knowledge_base_path_for_make(make: str) -> str:
    """Return knowledge base path for a vendor (Make)."""
    key = (make or "generic").strip().lower()
    return DEFAULT_KNOWLEDGE_BASE_BY_MAKE.get(key, "knowledge_base/generic")
