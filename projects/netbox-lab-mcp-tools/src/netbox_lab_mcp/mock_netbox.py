"""In-memory NetBox-like store for lab topology and reservation MCP tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import re
import uuid


def make_error(code: str, message: str) -> Dict[str, Any]:
    return {"error": True, "code": code, "message": message}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _parse_duration(value: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([mhdw])", value.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration: {value}")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)
    raise ValueError(f"Invalid duration: {value}")


@dataclass
class Site:
    id: int
    name: str
    slug: str


@dataclass
class Topology:
    id: int
    name: str
    slug: str
    site_id: int
    status: str = "draft"
    description: str = ""
    tenant: Optional[str] = None


@dataclass
class TopologyNode:
    id: int
    topology_id: int
    name: str
    device_type: str
    role: str


@dataclass
class TopologyLink:
    id: int
    topology_id: int
    label: str
    source_node: str
    source_interface: str
    target_node: str
    target_interface: str


@dataclass
class Reservation:
    id: int
    topology_id: int
    start: datetime
    end: datetime
    owner_username: str
    status: str = "scheduled"


class MockNetBox:
  """Minimal in-memory backend mirroring NetBox lab plugin concepts."""

  def __init__(self) -> None:
      self._sites: Dict[int, Site] = {}
      self._topologies: Dict[int, Topology] = {}
      self._nodes: Dict[int, TopologyNode] = {}
      self._links: Dict[int, TopologyLink] = {}
      self._reservations: Dict[int, Reservation] = {}
      self._next_id = 1

  def _next(self) -> int:
      value = self._next_id
      self._next_id += 1
      return value

  def ensure_site(self, name: str) -> Site:
      for site in self._sites.values():
          if site.name == name or site.slug == _slugify(name):
              return site
      site = Site(id=self._next(), name=name, slug=_slugify(name))
      self._sites[site.id] = site
      return site

  def create_topology(self, name: str, site: str, slug: Optional[str] = None, description: str = "") -> Dict[str, Any]:
      if not name:
          return make_error("VALIDATION_ERROR", "name is required")
      if not site:
          return make_error("VALIDATION_ERROR", "site is required")
      site_obj = self.ensure_site(site)
      slug_value = slug or _slugify(name)
      for topo in self._topologies.values():
          if topo.slug == slug_value:
              slug_value = f"{slug_value}-{topo.id}"
      topo = Topology(
          id=self._next(),
          name=name,
          slug=slug_value,
          site_id=site_obj.id,
          status="draft",
          description=description,
      )
      self._topologies[topo.id] = topo
      return self.serialize_topology(topo.id)

  def get_topology(self, topology_id: int) -> Dict[str, Any]:
      topo = self._topologies.get(topology_id)
      if not topo:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      payload = self.serialize_topology(topology_id)
      payload["nodes"] = [
          {"id": n.id, "name": n.name, "device_type": n.device_type, "role": n.role}
          for n in self._nodes.values()
          if n.topology_id == topology_id
      ]
      payload["links"] = [
          {
              "id": link.id,
              "label": link.label,
              "source_node": link.source_node,
              "target_node": link.target_node,
          }
          for link in self._links.values()
          if link.topology_id == topology_id
      ]
      return payload

  def list_topologies(self) -> Dict[str, Any]:
      items = [self.serialize_topology(t.id) for t in self._topologies.values()]
      return {"count": len(items), "results": items}

  def add_node(self, topology_id: int, name: str, device_type: str, role: str) -> Dict[str, Any]:
      if topology_id not in self._topologies:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      node = TopologyNode(
          id=self._next(),
          topology_id=topology_id,
          name=name,
          device_type=device_type,
          role=role,
      )
      self._nodes[node.id] = node
      return {"id": node.id, "name": node.name, "device_type": node.device_type, "role": node.role}

  def add_link(
      self,
      topology_id: int,
      label: str,
      source_node: str,
      source_interface: str,
      target_node: str,
      target_interface: str,
  ) -> Dict[str, Any]:
      if topology_id not in self._topologies:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      link = TopologyLink(
          id=self._next(),
          topology_id=topology_id,
          label=label,
          source_node=source_node,
          source_interface=source_interface,
          target_node=target_node,
          target_interface=target_interface,
      )
      self._links[link.id] = link
      return {"id": link.id, "label": link.label}

  def remove_node(self, node_id: int) -> Dict[str, Any]:
      node = self._nodes.pop(node_id, None)
      if not node:
          return make_error("NOT_FOUND", f"Node not found: {node_id}")
      self._links = {
          lid: link
          for lid, link in self._links.items()
          if link.topology_id != node.topology_id
          or link.source_node != node.name
          and link.target_node != node.name
      }
      return {"removed": node_id}

  def create_reservation(
      self,
      topology_id: int,
      start: datetime,
      end: datetime,
      owner_username: str = "lab",
  ) -> Dict[str, Any]:
      if topology_id not in self._topologies:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      if end <= start:
          return make_error("VALIDATION_ERROR", "end must be after start")
      reservation = Reservation(
          id=self._next(),
          topology_id=topology_id,
          start=start,
          end=end,
          owner_username=owner_username,
      )
      self._reservations[reservation.id] = reservation
      return {
          "id": reservation.id,
          "topology_id": topology_id,
          "status": reservation.status,
          "start": start.isoformat(),
          "end": end.isoformat(),
          "owner_username": owner_username,
      }

  def resolve_topology(self, topology_id: int) -> Dict[str, Any]:
      topo = self._topologies.get(topology_id)
      if not topo:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      topo.status = "resolved"
      return {"id": topo.id, "status": topo.status}

  def release_topology(self, topology_id: int) -> Dict[str, Any]:
      topo = self._topologies.get(topology_id)
      if not topo:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      topo.status = "draft"
      return {"id": topo.id, "status": topo.status}

  def check_conflicts(self, topology_id: Optional[int] = None) -> Dict[str, Any]:
      if topology_id is not None and topology_id not in self._topologies:
          return make_error("NOT_FOUND", f"Topology not found: {topology_id}")
      return {"conflict_count": 0, "conflicts": []}

  def serialize_topology(self, topology_id: int) -> Dict[str, Any]:
      topo = self._topologies[topology_id]
      site = self._sites[topo.site_id]
      return {
          "id": topo.id,
          "name": topo.name,
          "slug": topo.slug,
          "status": topo.status,
          "site": site.name,
          "description": topo.description,
      }


# Module-level default store for MCP server and tests
STORE = MockNetBox()
