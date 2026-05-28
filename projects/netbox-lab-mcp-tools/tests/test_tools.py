from datetime import datetime, timedelta, timezone

import pytest

from netbox_lab_mcp.mock_netbox import MockNetBox, _parse_duration
from netbox_lab_mcp import tools


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    store = MockNetBox()
    monkeypatch.setattr(tools, "STORE", store)
    yield store


def test_parse_duration():
    assert _parse_duration("30m") == timedelta(minutes=30)
    assert _parse_duration("2h") == timedelta(hours=2)
    with pytest.raises(ValueError):
        _parse_duration("5y")


def test_create_and_get_topology():
    created = tools.create_topology_tool(name="Test Topo", site="Lab")
    assert created["name"] == "Test Topo"
    assert created["status"] == "draft"
    fetched = tools.get_topology_tool(created["id"])
    assert fetched["name"] == "Test Topo"
    assert "nodes" in fetched


def test_list_topologies():
    tools.create_topology_tool(name="Topo 1", site="Lab")
    tools.create_topology_tool(name="Topo 2", site="Lab")
    result = tools.list_topologies_tool()
    assert result["count"] == 2


def test_add_node_and_link():
    topo = tools.create_topology_tool(name="Link Test", site="Lab")
    tools.add_node_tool(topo["id"], "SW1", "TestSwitch", "Switch")
    tools.add_node_tool(topo["id"], "SW2", "TestSwitch", "Switch")
    link = tools.add_link_tool(topo["id"], "uplink", "SW1", "eth0", "SW2", "eth0")
    assert link["label"] == "uplink"


def test_create_reservation_validation():
    topo = tools.create_topology_tool(name="Res Test", site="Lab")
    tools.resolve_topology_tool(topo["id"])
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=2)
    result = tools.create_reservation_tool(
        topology_id=topo["id"],
        start=start.isoformat(),
        end=end.isoformat(),
        owner_username="tester",
    )
    assert "id" in result
    assert result["status"] == "scheduled"


def test_create_reservation_invalid_topology():
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    result = tools.create_reservation_tool(99999, start.isoformat(), end.isoformat())
    assert result["error"]
    assert result["code"] == "NOT_FOUND"


def test_resolve_and_release():
    topo = tools.create_topology_tool(name="Resolve", site="Lab")
    assert tools.resolve_topology_tool(topo["id"])["status"] == "resolved"
    assert tools.release_topology_tool(topo["id"])["status"] == "draft"


def test_check_conflicts():
    assert tools.check_conflicts_tool()["conflict_count"] == 0
