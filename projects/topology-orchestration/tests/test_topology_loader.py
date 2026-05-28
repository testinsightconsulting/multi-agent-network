from pathlib import Path

import pytest

from topology_orchestration.topology_loader import load_topology

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_load_zero_touch_lab_devices():
    topo = load_topology(str(EXAMPLES / "zero_touch_lab.yaml"))
    assert topo.name
    assert len(topo.devices) == 2
    ids = {d.inventory_id for d in topo.devices}
    assert "11111111-1111-4111-8111-111111111101" in ids
    assert topo.get_device_by_inventory_id("22222222-2222-4222-8222-222222222202").make == "juniper"


def test_agent_id_equals_inventory_id():
    topo = load_topology(str(EXAMPLES / "zero_touch_lab.yaml"))
    for device in topo.devices:
        assert device.agent_id == device.inventory_id


def test_layer3_crossover_ports_and_links():
    topo = load_topology(str(EXAMPLES / "layer3_crossover.yaml"))
    assert len(topo.devices) == 2
    assert len(topo.ports) == 2
    assert len(topo.links) == 1


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        load_topology("does-not-exist.yaml")
