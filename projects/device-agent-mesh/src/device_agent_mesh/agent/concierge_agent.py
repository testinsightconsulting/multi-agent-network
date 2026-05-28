"""Concierge Agent - single entry point for users; routes questions to specialist agents."""
import asyncio
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from device_agent_mesh.agent.message_bus import MessageBus, AgentMessage
from device_agent_mesh.agent.agent_registry import AgentRegistry
from device_agent_mesh.utils.debug_helper import debug
from device_agent_mesh.utils.api_helper import generate_content_with_adaptive_retry

CONCIERGE_AGENT_ID = "concierge"


@dataclass
class SpecialistInfo:
    """One specialist (device) in the topology."""
    id: str  # inventory_id or agent_id
    name: str
    type: str
    ip: str = ""
    model: str = ""


@dataclass
class TopologyOverview:
    """Overview of the topology for the concierge (devices/specialists only)."""
    name: str
    specialists: List[SpecialistInfo] = field(default_factory=list)


class ConciergeAgent:
    """
    Topology concierge: the only agent users talk to.
    Discovers devices from the topology and redirects user questions to the
    appropriate specialist agent(s) by inventory_id (or agent_id).
    """

    def __init__(
        self,
        topology_overview: TopologyOverview,
        gemini_api_key: str,
        message_bus: MessageBus,
        agent_registry: AgentRegistry,
    ):
        self.topology_overview = topology_overview
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.conversations: Dict[str, List[types.Content]] = {}

        self.agent_registry.register_agent(
            agent_id=CONCIERGE_AGENT_ID,
            agent_name="Topology Concierge",
            agent_type="concierge",
            capabilities=["topology_overview", "route_to_specialist", "query_specialists"],
        )
        self.message_bus.subscribe(CONCIERGE_AGENT_ID, self._handle_message)

    def _build_system_instruction(self) -> str:
        return """You are the Topology Concierge for a network. Users always talk to you—never directly to device specialists.

Your role:
1. Understand the user's question in the context of the network topology.
2. Use get_topology_overview to see which devices (specialists) exist and their IDs.
3. Route questions to the right specialist(s) using query_specialist with the specialist's ID (inventory_id or agent_id).
4. Synthesize specialist responses and answer the user clearly. If you query multiple specialists, combine the information.

Rules:
- Never tell the user to contact a specialist directly. You always route and respond.
- Use query_specialist(agent_id, question) to ask a device's specialist; agent_id is the UUID (inventory_id) or agent_id shown in the topology overview.
- For topology-wide questions (e.g. "list all devices"), use get_topology_overview and summarize.
- For device-specific questions (e.g. "what is the BGP config on the Arista?"), identify the right specialist ID from the overview, then query_specialist.
- For multi-device questions, call query_specialist for each relevant device and synthesize.
- SPECIAL POLICY FOR vSTC (Spirent): When the user asks about a Spirent device (vSTC), limit your diagnosis and specialist queries ONLY to ascertaining if it is reachable (via ping from other devices). Do not ask specialists for deep configuration analysis of Spirent devices.
"""

    def _create_tools(self) -> List:
        return [
            self.get_topology_overview,
            self.query_specialist,
            self.query_multiple_specialists,
        ]

    def get_topology_overview(self) -> Dict[str, Any]:
        """Returns the current topology: name and list of devices (specialists) with their ID, name, type, and IP.
        Use this to see which specialists exist and their IDs before routing questions."""
        return {
            "status": "success",
            "topology_name": self.topology_overview.name,
            "specialists": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type,
                    "ip": s.ip or "(not set)",
                    "model": s.model or "",
                }
                for s in self.topology_overview.specialists
            ],
            "hint": "Use the 'id' field as agent_id when calling query_specialist(agent_id, question).",
        }

    def query_specialist(
        self,
        agent_id: str,
        question: str,
        conversation_id: str = None,
    ) -> Dict[str, Any]:
        """Sends a question to the specialist agent for a specific device and returns their response.
        agent_id: the specialist's ID (inventory_id UUID or agent_id from topology overview).
        question: the question to ask that device's specialist (e.g. config, diagnostics)."""
        if agent_id == CONCIERGE_AGENT_ID:
            return {"status": "error", "message": "Cannot query the concierge as a specialist."}

        if not self.agent_registry.agent_exists(agent_id):
            return {
                "status": "error",
                "message": f"Specialist {agent_id} not found. Use get_topology_overview to see valid specialist IDs.",
            }

        # BREAKPOINT: Concierge calling specialist (before message is sent)
        debug("Concierge calling specialist", to_agent=agent_id, question=question[:80])

        msg = AgentMessage(
            from_agent=CONCIERGE_AGENT_ID,
            to_agent=agent_id,
            message_type="query",
            content=question,
            conversation_id=conversation_id or f"concierge_{datetime.now().isoformat()}",
        )
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # With nest_asyncio applied in CLI, nested run_until_complete works so we can wait for specialist response
        try:
            response = loop.run_until_complete(
                self.message_bus.send_and_wait(msg, timeout=30)
            )
            # BREAKPOINT: Concierge received response from specialist
            debug("Concierge received response from specialist", specialist_id=agent_id, has_response=response is not None)
            return {
                "status": "success",
                "specialist_id": agent_id,
                "question": question,
                "response": response.content if response else "No response received",
            }
        except Exception as e:
            debug("Concierge query_specialist error", specialist_id=agent_id, error=str(e))
            return {"status": "error", "message": str(e)}

    def query_multiple_specialists(
        self,
        agent_ids: List[str],
        question: str,
        conversation_id: str = None,
    ) -> Dict[str, Any]:
        """Asks the same question to multiple specialist agents and returns all responses.
        agent_ids: list of specialist IDs (inventory_id or agent_id).
        question: the question to ask each specialist."""
        results = []
        for aid in agent_ids:
            r = self.query_specialist(aid, question, conversation_id)
            results.append({"agent_id": aid, **r})
        return {
            "status": "success",
            "question": question,
            "responses": results,
        }

    async def _handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle incoming messages (e.g. if another agent asks the concierge something)."""
        response_text = await self._process_query(
            message.content,
            message.conversation_id or message.message_id,
        )
        return AgentMessage(
            from_agent=CONCIERGE_AGENT_ID,
            to_agent=message.from_agent,
            message_type="response",
            content=response_text,
            conversation_id=message.conversation_id,
        )

    async def _process_query(self, query: str, conversation_id: str) -> str:
        history = self.conversations.get(conversation_id, [])
        history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=query)])
        )
        
        current_history = history
        max_turns = 10
        
        for _ in range(max_turns):
            response = self._generate_content_with_retry(current_history)
            if not response or not response.candidates:
                return "Error: No response from concierge."
            
            candidate = response.candidates[0]
            current_history.append(candidate.content)
            
            # Check for function calls
            function_calls = []
            for part in candidate.content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)
            
            if function_calls:
                tool_outputs = []
                for fc in function_calls:
                    debug(f"Concierge executing tool: {fc.name}", args=fc.args)
                    tool_func = getattr(self, fc.name, None)
                    if tool_func:
                        try:
                            # Handle tool execution
                            # Note: tools like query_specialist might be async or sync?
                            # Defined tools are sync methods in the class: query_specialist -> sync method but calls async loop?
                            # query_specialist uses 'loop.run_until_complete' internally to match sync signature expected by Gemini?
                            # Yes, existing code uses loop.run_until_complete inside query_specialist.
                            # Inject conversation_id into tools that support it to maintain context
                            args = dict(fc.args)
                            if fc.name in ["query_specialist", "query_multiple_specialists"] and "conversation_id" not in args:
                                args["conversation_id"] = conversation_id
                            
                            result = tool_func(**args)
                            tool_outputs.append(types.Part.from_function_response(
                                name=fc.name,
                                response={"result": result}
                            ))
                        except Exception as e:
                            tool_outputs.append(types.Part.from_function_response(
                                name=fc.name,
                                response={"error": str(e)}
                            ))
                    else:
                        tool_outputs.append(types.Part.from_function_response(
                            name=fc.name,
                            response={"error": f"Tool {fc.name} not found"}
                        ))
                
                current_history.append(types.Content(
                    role="user",
                    parts=tool_outputs
                ))
            else:
                self.conversations[conversation_id] = current_history
                return response.text or ""
                
        return "Error: Maximum conversation turns exceeded."

    def _generate_content_with_retry(
        self,
        history: List[types.Content],
        max_retries: int = 5,
    ):
        """Generate content using the adaptive api_helper."""
        return generate_content_with_adaptive_retry(
            client=self.gemini_client,
            model="gemini-2.5-flash",
            history=history,
            system_instruction=self._build_system_instruction(),
            tools=self._create_tools(),
            max_retries=max_retries,
            agent_id="Concierge"
        )

    async def chat(self, user_input: str, conversation_id: Optional[str] = None) -> str:
        """Main entry: user talks to the concierge; concierge routes to specialists and responds."""
        cid = conversation_id or f"user_{CONCIERGE_AGENT_ID}_{datetime.now().isoformat()}"
        return await self._process_query(user_input, cid)
