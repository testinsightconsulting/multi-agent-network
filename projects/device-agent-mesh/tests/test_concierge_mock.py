"""Pytest for Concierge + specialist flow with mocked Gemini and SSH."""
import asyncio
import os
from unittest.mock import MagicMock, patch

import nest_asyncio
import pytest

from device_agent_mesh.agent.agent_registry import AgentRegistry
from device_agent_mesh.agent.concierge_agent import ConciergeAgent
from device_agent_mesh.agent.message_bus import MessageBus
from device_agent_mesh.cli.agent_cli import _build_topology_overview, _create_agents_from_simple_topology


def _mock_gemini_response(function_calls=None, text=None):
    response = MagicMock()
    response.text = text or "Specialist reports all interfaces are up."
    response.candidates = [MagicMock()]
    part = MagicMock()
    if function_calls:
        part.function_call.name = function_calls[0]["name"]
        part.function_call.args = function_calls[0]["args"]
        part.text = None
    else:
        part.function_call = None
        part.text = response.text
    response.candidates[0].content.parts = [part]
    return response


class MockGeminiClient:
    def __init__(self):
        self.call_count = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.call_count += 1
        return _mock_gemini_response()


def test_concierge_routes_to_specialist():
    nest_asyncio.apply()
    asyncio.run(_run_concierge_test())


async def _run_concierge_test():
    topology_config = {
        "topology": {
            "name": "Mock Lab",
            "agents": [
                {
                    "agent_id": "switch1",
                    "device_name": "Arista-Switch",
                    "device_type": "arista",
                    "model": "DCS-7050",
                    "os_version": "EOS 4.20",
                    "management_ip": "192.168.1.10",
                    "commands": {"show_int": "show interfaces"},
                    "knowledge_base_path": "knowledge_base/generic",
                }
            ],
        }
    }

    message_bus = MessageBus()
    agent_registry = AgentRegistry()
    rag_engine = MagicMock()
    web_search = MagicMock()
    await message_bus.start()

    with patch("device_agent_mesh.cli.agent_cli.GenericSshDeviceInterface") as mock_ssh_cls:
        mock_ssh = MagicMock()
        mock_ssh_cls.return_value = mock_ssh
        mock_ssh.execute_command.return_value = "Et1 connected"
        mock_ssh.get_configuration.return_value = {}

        agents = _create_agents_from_simple_topology(
            topology_config,
            message_bus,
            agent_registry,
            rag_engine,
            web_search,
            "mock_key",
        )
        for agent in agents.values():
            agent.gemini_client = MockGeminiClient()

        overview = _build_topology_overview(agents, "Mock Topology")
        concierge = ConciergeAgent(overview, "mock_key", message_bus, agent_registry)
        concierge.gemini_client = MockGeminiClient()

        response = await concierge.chat("What is the status of the Arista switch?")
        assert response
        assert isinstance(response, str)

    await message_bus.stop()


def test_import_package():
    import device_agent_mesh  # noqa: F401

    assert device_agent_mesh.__version__
