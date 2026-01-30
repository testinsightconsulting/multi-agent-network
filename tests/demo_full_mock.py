
import asyncio
import os
import yaml
import sys
from unittest.mock import MagicMock, patch
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import nest_asyncio
from src.agent.message_bus import MessageBus
from src.agent.agent_registry import AgentRegistry
from src.knowledge.rag_engine import RAGEngine
from src.knowledge.web_search import WebSearch
from src.cli.agent_cli import _create_agents_from_simple_topology, _build_topology_overview
from src.agent.concierge_agent import ConciergeAgent
from google.genai import types

# --- Mocks for Gemini Response ---

def mock_function_call(name, args):
    part = MagicMock()
    part.function_call.name = name
    part.function_call.args = args
    part.text = None
    return part

def mock_text_response(text):
    part = MagicMock()
    part.function_call = None
    part.text = text
    return part

def create_mock_response(parts):
    response = MagicMock()
    candidate = MagicMock()
    content = MagicMock()
    content.parts = parts
    candidate.content = content
    response.candidates = [candidate]
    response.text = parts[0].text if parts[0].text else None # Simplify for simple text
    return response

# We need to statefully mock the LLM interactions.
# Flow:
# 1. User -> Concierge: "state of switch?"
# 2. Concierge LLM -> Tool Call: query_specialist(switch1, "state?")
# 3. Concierge executes tool -> MessageBus -> Specialist
# 4. Specialist LLM -> Tool Call: execute_device_command("show interfaces")
# 5. Specialist executes tool -> MockSSH -> "Gi0/0 UP"
# 6. Specialist LLM -> Text Response: "The switch interfaces are UP."
# 7. Concierge receives response.
# 8. Concierge LLM -> Text Response: "The Arista switch is working correctly."

class MockGeminiClient:
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.call_count = 0

    def generate_content(self, model, contents, config=None):
        self.call_count += 1
        
        # --- Concierge Logic ---
        if "Concierge" in self.agent_name:
            # First call: User asks question -> Call query_specialist
            if self.call_count == 1:
                return create_mock_response([
                    mock_function_call("query_specialist", {"agent_id": "switch1", "question": "Check the detailed status of the switch interfaces."})
                ])
            # Second call: After getting tool result -> Final Answer
            else:
                 return create_mock_response([
                    mock_text_response("Based on the specialist's report, the Arista switch (switch1) interfaces are all UP and functioning normally.")
                ])

        # --- Specialist Logic ---
        else: # switch1
             # First call: Receives query -> Call execute_device_command
            if self.call_count == 1:
                return create_mock_response([
                    mock_function_call("execute_device_command", {"command": "show interfaces status"})
                ])
            # Second call: After getting command output -> Final Answer
            else:
                 return create_mock_response([
                    mock_text_response("I have checked the system. The command 'show interfaces status' indicates that Ethernet1 and Ethernet2 are 'connected' and UP.")
                ])
        return create_mock_response([mock_text_response("Error: Unexpected mock state")])

    @property
    def models(self):
        # The code calls client.models.generate_content
        return self

# --- Main Test Script ---

async def run_demo():
    print("--- Starting Full Mock Demonstration ---")
    
    # 1. Setup Mock SSH
    print("[System] Setting up Mock SSH Interface...")
    with patch('src.cli.agent_cli.GenericSshDeviceInterface') as MockSSH:
        mock_ssh = MagicMock()
        MockSSH.return_value = mock_ssh
        mock_ssh.execute_command.return_value = """
Port      Name        Status       Vlan       Duplex  Speed Type
Et1       Uplink      connected    1          full    10G   10GBASE-T
Et2       Host        connected    1          full    1G    1000BASE-T
"""
        mock_ssh.get_configuration.return_value = {}

        # 2. Setup Topology (Simple)
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
                        "management_ip": "1.2.3.4", # Triggers SSH flow
                        "commands": {"show_int": "show interfaces"},
                        "knowledge_base_path": "knowledge_base/generic"
                    }
                ]
            }
        }

        # 3. Initialize Infrastructure
        message_bus = MessageBus()
        agent_registry = AgentRegistry()
        rag_engine = MagicMock() # Mock RAG too
        web_search = MagicMock()
        
        await message_bus.start()

        # 4. Create Agents with Mocked Gemini Client
        # We need to patch genai.Client to return our stateful MockGeminiClient
        
        with patch('google.genai.Client') as MockClientIs:
             # When Client(api_key=...) is called, we need to know WHICH agent is calling it.
             # But the class instantiation happens inside DeviceAgent/ConciergeAgent __init__.
             # We can use a side_effect to return different mocks, but simpler is to
             # patch the agents to inject our mock client *after* creation or patch the class.
             
             # Let's use a simpler approach: Initialize agents, then swap their clients.
             
             # Env vars for SSH
             os.environ["SSH_ENABLED"] = "true"
             os.environ["SSH_USERNAME"] = "mockuser"
             os.environ["SSH_PASSWORD"] = "mockpass"
             
             print("[System] Creating Agents...")
             agents = _create_agents_from_simple_topology(
                 topology_config, message_bus, agent_registry, rag_engine, web_search, "mock_key"
             )
             specialist = agents["switch1"]
             specialist.gemini_client = MockGeminiClient("switch1")
             
             overview = _build_topology_overview(agents, "Mock Topology")
             concierge = ConciergeAgent(overview, "mock_key", message_bus, agent_registry)
             concierge.gemini_client = MockGeminiClient("Concierge")

             # 5. Run Interaction
             print("\n[User] 'What is the state of the Arista switch?'")
             response = await concierge.chat("What is the state of the Arista switch?")
             
             print(f"\n[Concierge Response] {response}")

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(run_demo())
