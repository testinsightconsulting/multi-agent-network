"""Topology loading and discovery for orchestration topologies (TOSCA/Spirent Velocity)."""
from src.topology.topology_loader import (
    load_topology,
    Topology,
    DeviceNode,
    PortNode,
    EthernetLinkNode,
    is_orchestration_topology,
    get_default_commands_for_make,
    get_knowledge_base_path_for_make,
)

__all__ = [
    "load_topology",
    "Topology",
    "DeviceNode",
    "PortNode",
    "EthernetLinkNode",
    "is_orchestration_topology",
    "get_default_commands_for_make",
    "get_knowledge_base_path_for_make",
]
