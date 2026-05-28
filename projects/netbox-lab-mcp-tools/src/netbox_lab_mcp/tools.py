"""MCP tool functions backed by the in-memory MockNetBox store."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from netbox_lab_mcp.mock_netbox import STORE, _parse_duration, make_error


def create_topology_tool(
    name: str,
    site: str,
    slug: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    return STORE.create_topology(name=name, site=site, slug=slug, description=description)


def get_topology_tool(topology_id: int) -> Dict[str, Any]:
    return STORE.get_topology(topology_id)


def list_topologies_tool() -> Dict[str, Any]:
    return STORE.list_topologies()


def add_node_tool(
    topology_id: int,
    name: str,
    device_type: str,
    role: str,
) -> Dict[str, Any]:
    return STORE.add_node(topology_id, name, device_type, role)


def add_link_tool(
    topology_id: int,
    label: str,
    source_node: str,
    source_interface: str,
    target_node: str,
    target_interface: str,
) -> Dict[str, Any]:
    return STORE.add_link(
        topology_id,
        label,
        source_node,
        source_interface,
        target_node,
        target_interface,
    )


def remove_node_tool(node_id: int) -> Dict[str, Any]:
    return STORE.remove_node(node_id)


def create_reservation_tool(
    topology_id: int,
    start: str,
    end: str,
    owner_username: str = "lab",
) -> Dict[str, Any]:
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return make_error("VALIDATION_ERROR", "start and end must be ISO-8601 datetimes")
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    return STORE.create_reservation(topology_id, start_dt, end_dt, owner_username)


def create_reservation_with_duration_tool(
    topology_id: int,
    duration: str,
    owner_username: str = "lab",
) -> Dict[str, Any]:
    try:
        delta = _parse_duration(duration)
    except ValueError as exc:
        return make_error("VALIDATION_ERROR", str(exc))
    start_dt = datetime.now(timezone.utc)
    end_dt = start_dt + delta
    return STORE.create_reservation(topology_id, start_dt, end_dt, owner_username)


def resolve_topology_tool(topology_id: int) -> Dict[str, Any]:
    return STORE.resolve_topology(topology_id)


def release_topology_tool(topology_id: int) -> Dict[str, Any]:
    return STORE.release_topology(topology_id)


def check_conflicts_tool(topology_id: Optional[int] = None) -> Dict[str, Any]:
    return STORE.check_conflicts(topology_id)
