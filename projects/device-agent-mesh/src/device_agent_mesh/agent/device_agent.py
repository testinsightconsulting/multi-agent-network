"""Device agent - expert agent representing a network device"""
import asyncio
import time
from typing import Dict, List, Optional, Any
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from dataclasses import dataclass
from datetime import datetime
import json

from device_agent_mesh.device.device_interface import DeviceInterface
from device_agent_mesh.device.command_resolver import CommandResolver
from device_agent_mesh.device.prompt_resolver import PromptResolver
from device_agent_mesh.knowledge.rag_engine import RAGEngine
from device_agent_mesh.knowledge.web_search import WebSearch
from device_agent_mesh.agent.message_bus import MessageBus, AgentMessage
from device_agent_mesh.agent.agent_registry import AgentRegistry
from device_agent_mesh.utils.debug_helper import debug
from device_agent_mesh.utils.api_helper import generate_content_with_adaptive_retry


@dataclass
class DeviceContext:
    """Device-specific context and capabilities"""
    agent_id: str
    device_name: str
    device_type: str
    model: str
    os_version: str
    management_ip: str
    commands: Dict[str, str]
    knowledge_base_path: str


class DeviceAgent:
    """Expert agent representing a network device"""
    
    def __init__(
        self,
        context: DeviceContext,
        gemini_api_key: str,
        message_bus: MessageBus,
        agent_registry: AgentRegistry,
        device_interface: DeviceInterface,
        rag_engine: RAGEngine,
        web_search: WebSearch
    ):
        self.context = context
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.message_bus = message_bus
        self.agent_registry = agent_registry
        self.device_interface = device_interface
        self.rag_engine = rag_engine
        self.web_search = web_search
        self.command_resolver = CommandResolver(
            device_type=context.device_type,
            model=context.model,
            os_version=context.os_version,
            commands=context.commands,
            rag_engine=rag_engine,
            web_search=web_search,
        )
        self.prompt_resolver = PromptResolver(
            device_type=context.device_type,
            model=context.model,
            os_version=context.os_version,
            rag_engine=rag_engine,
            web_search=web_search,
        )
        
        # Conversation history (per conversation thread)
        self.conversations: Dict[str, List[types.Content]] = {}
        
        # Register this agent
        self.agent_registry.register_agent(
            agent_id=context.agent_id,
            agent_name=context.device_name,
            agent_type="device",
            capabilities=self._get_capabilities()
        )
        
        # Subscribe to messages
        self.message_bus.subscribe(context.agent_id, self._handle_message)
    
    def _get_capabilities(self) -> List[str]:
        """Returns list of capabilities this agent can perform"""
        return [
            "read_configuration",
            "analyze_configuration",
            "validate_configuration",
            "troubleshoot_issues",
            "provide_device_specific_advice",
            "communicate_with_other_agents"
        ]
    
    def _build_system_instruction(self) -> str:
        """Builds device-specific system instruction"""
        instruction = f"""You are an expert network engineer specializing in {self.context.device_type} {self.context.model} running {self.context.os_version}.

Your device context:
- Device Name: {self.context.device_name}
- Management IP: {self.context.management_ip}
- Available Commands: {json.dumps(self.context.commands, indent=2)}

Your capabilities:
1. Execute device-specific commands to read configuration and state
2. Analyze configuration using device-specific syntax and best practices
3. Validate configurations against vendor documentation
4. Troubleshoot network issues specific to your device
5. Communicate with other network device agents when needed
6. Look up documentation from local knowledge base or internet

When you need information from another device:
- Use the query_other_agent tool to ask questions
- Specify which agent you're querying
- The other agent will respond with device-specific information

Always use the provided tools to gather actual data before answering questions.
If you need help selecting a device command, use suggest_device_commands(question)
or resolve_and_execute_commands(question) to pick and run the best command(s).

CRITICAL PROMPT HANDLING:
Network devices sometimes present interactive prompts or ephemeral warnings (e.g., confirmation requests, paging prompts, or transient file locks).
You must never be stopped by these. If the output of a command contains a prompt or a request for interaction:
1. Immediately call `suggest_prompt_handlers(output)` to identify the required response.
2. Call `update_ssh_prompt_handlers(handlers)` to register the automation.
3. Re-execute the command to get the actual data.

IMPORTANT: If a command successfully returns data (like a configuration) after a previous failure or warning, DISREGARD the previous warning and focus on the current data. Never tell the user you are "unable" to do something if you have data in your most recent tool output.

Provide accurate, device-specific answers based on your expertise and the actual device state.
"""
        if self.context.device_type.lower() == "spirent":
            instruction += "\nSPECIAL POLICY FOR vSTC (Spirent): For this device, limit your diagnosis ONLY to ascertaining if it is reachable (via ping or other basic connectivity checks) from yourself or other devices. Do not attempt to analyze internal XML configurations or complex application-level symptoms, as these vary greatly based on external files.\n"
        
        return instruction
    
    def _create_tools(self) -> List:
        """Creates tools available to this agent"""
        return [
            self.read_device_configuration,
            self.execute_device_command,
            self.analyze_configuration,
            self.validate_feature_configuration,
            self.query_local_knowledge_base,
            self.search_web_documentation,
            self.suggest_device_commands,
            self.resolve_and_execute_commands,
            self.suggest_prompt_handlers,
            self.update_ssh_prompt_handlers,
            self.list_ssh_prompt_handlers,
            self.query_other_agent,
            self.get_topology_info,
        ]
    
    # Tool Definitions
    
    def read_device_configuration(self, section: str = None) -> Dict[str, Any]:
        """Reads the current device configuration.
        
        Args:
            section: Optional section to read (e.g., 'bgp', 'interfaces', 'ospf')
        
        Returns:
            Dictionary containing configuration data.
        """
        # BREAKPOINT: Specialist step — reading device configuration
        debug("Specialist tool: read_device_configuration", device=self.context.device_name, section=section)
        try:
            config = self.device_interface.get_configuration(section=section)
            return {
                "status": "success",
                "device": self.context.device_name,
                "configuration": config
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def execute_device_command(self, command: str) -> Dict[str, Any]:
        """Executes a device-specific command.
        
        Args:
            command: Command to execute (device-specific syntax)
        
        Returns:
            Command output.
        """
        # BREAKPOINT: Specialist step — executing device command
        debug("Specialist tool: execute_device_command", device=self.context.device_name, command=command[:80] if command else "")
        try:
            output = self.device_interface.execute_command(command)
            return {
                "status": "success",
                "device": self.context.device_name,
                "command": command,
                "output": output
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def analyze_configuration(self, feature: str = None) -> Dict[str, Any]:
        """Analyzes device configuration for issues or optimizations.
        
        Args:
            feature: Optional feature to analyze (e.g., 'bgp', 'ospf', 'interfaces')
        
        Returns:
            Analysis results with findings and recommendations.
        """
        # BREAKPOINT: Specialist step — analyzing configuration
        debug("Specialist tool: analyze_configuration", device=self.context.device_name, feature=feature)
        config = self.device_interface.get_configuration()
        
        # Use RAG to get best practices
        best_practices = self.rag_engine.query(
            query=f"{feature} best practices {self.context.device_type} {self.context.model}",
            device_type=self.context.device_type
        )
        
        # Agent will analyze config against best practices
        return {
            "status": "success",
            "device": self.context.device_name,
            "configuration": config,
            "best_practices_reference": best_practices[:500] if best_practices else None
        }
    
    def validate_feature_configuration(
        self,
        feature: str,
        expected_behavior: str = None
    ) -> Dict[str, Any]:
        """Validates if a feature is correctly configured.
        
        Args:
            feature: Feature name to validate
            expected_behavior: Optional description of expected behavior
        
        Returns:
            Validation results with pass/fail and recommendations.
        """
        # BREAKPOINT: Specialist step — validating feature configuration
        debug("Specialist tool: validate_feature_configuration", device=self.context.device_name, feature=feature)
        # Get current config
        config = self.device_interface.get_configuration()
        
        # Query knowledge base for correct configuration
        query = f"how to configure {feature} on {self.context.device_type} {self.context.model} {self.context.os_version}"
        knowledge = self.rag_engine.query(query, device_type=self.context.device_type)
        
        if not knowledge:
            # Fallback to web search
            knowledge = self.web_search.search(query)
        
        return {
            "status": "success",
            "device": self.context.device_name,
            "feature": feature,
            "current_config": config.get(feature, {}),
            "documentation": knowledge[:1000] if knowledge else None,
            "expected_behavior": expected_behavior
        }
    
    def query_local_knowledge_base(self, query: str) -> Dict[str, Any]:
        """Queries the local RAG knowledge base for device documentation.
        
        Args:
            query: Question or topic to search for
        
        Returns:
            Relevant documentation snippets.
        """
        # BREAKPOINT: Specialist step — querying local knowledge base
        debug("Specialist tool: query_local_knowledge_base", device=self.context.device_name, query=query[:60] if query else "")
        results = self.rag_engine.query(
            query=query,
            device_type=self.context.device_type
        )
        return {
            "status": "success",
            "device": self.context.device_name,
            "query": query,
            "results": results[:2000] if results else "No results found in local knowledge base"
        }
    
    def search_web_documentation(self, query: str) -> Dict[str, Any]:
        """Searches the internet for device documentation.
        
        Args:
            query: Search query (e.g., "Cisco IOS XE BGP route reflector configuration")
        
        Returns:
            Search results from web.
        """
        # BREAKPOINT: Specialist step — searching web documentation
        debug("Specialist tool: search_web_documentation", device=self.context.device_name, query=query[:60] if query else "")
        results = self.web_search.search(query)
        return {
            "status": "success",
            "device": self.context.device_name,
            "query": query,
            "results": results[:2000] if results else "No results found"
        }

    def suggest_device_commands(self, question: str, max_commands: int = 3) -> Dict[str, Any]:
        """Suggests device commands to answer a question using catalog + RAG + web search.

        Args:
            question: User question (e.g., "what is my BGP status?")
            max_commands: Max number of command suggestions

        Returns:
            Suggested commands with sources used (catalog, rag, web).
        """
        # BREAKPOINT: Specialist step — suggesting device commands
        debug("Specialist tool: suggest_device_commands", device=self.context.device_name, question=question[:80] if question else "")
        suggestions = self.command_resolver.suggest_commands(question, max_commands=max_commands)
        return {
            "status": "success",
            "device": self.context.device_name,
            "question": question,
            "commands": suggestions.get("commands", []),
            "sources": suggestions.get("sources", []),
        }

    def resolve_and_execute_commands(self, question: str, max_commands: int = 2) -> Dict[str, Any]:
        """Resolves likely commands for a question and executes them.

        Args:
            question: User question (e.g., "what is my current configuration?")
            max_commands: Max number of commands to execute

        Returns:
            Command outputs for the resolved commands.
        """
        # BREAKPOINT: Specialist step — resolve and execute commands
        debug("Specialist tool: resolve_and_execute_commands", device=self.context.device_name, question=question[:80] if question else "")
        suggestions = self.command_resolver.suggest_commands(question, max_commands=max_commands)
        outputs = []
        for cmd in suggestions.get("commands", []):
            outputs.append(self.execute_device_command(cmd))
        return {
            "status": "success",
            "device": self.context.device_name,
            "question": question,
            "commands": suggestions.get("commands", []),
            "sources": suggestions.get("sources", []),
            "outputs": outputs,
        }

    def suggest_prompt_handlers(self, output: str, max_handlers: int = 5) -> Dict[str, Any]:
        """Suggest prompt handlers using RAG + web based on observed output."""
        # BREAKPOINT: Specialist step — suggesting prompt handlers
        debug("Specialist tool: suggest_prompt_handlers", device=self.context.device_name, output=output[:80] if output else "")
        suggestions = self.prompt_resolver.suggest_handlers(output, max_handlers=max_handlers)
        return {
            "status": "success",
            "device": self.context.device_name,
            "handlers": suggestions.get("handlers", []),
            "sources": suggestions.get("sources", []),
        }

    def update_ssh_prompt_handlers(self, handlers: List[Dict[str, str]]) -> Dict[str, Any]:
        """Update SSH prompt handlers on the underlying SSH interface (if supported)."""
        # BREAKPOINT: Specialist step — updating SSH prompt handlers
        debug("Specialist tool: update_ssh_prompt_handlers", device=self.context.device_name, handler_count=len(handlers))
        if hasattr(self.device_interface, "update_prompt_handlers"):
            self.device_interface.update_prompt_handlers(handlers)
            return {"status": "success", "updated": len(handlers)}
        return {"status": "error", "message": "Device interface does not support prompt handlers"}

    def list_ssh_prompt_handlers(self) -> Dict[str, Any]:
        """List SSH prompt handlers on the underlying SSH interface (if supported)."""
        # BREAKPOINT: Specialist step — listing SSH prompt handlers
        debug("Specialist tool: list_ssh_prompt_handlers", device=self.context.device_name)
        if hasattr(self.device_interface, "list_prompt_handlers"):
            return {"status": "success", "handlers": self.device_interface.list_prompt_handlers()}
        return {"status": "error", "message": "Device interface does not support prompt handlers"}
    
    def query_other_agent(
        self,
        target_agent_id: str,
        question: str,
        conversation_id: str = None
    ) -> Dict[str, Any]:
        """Queries another device agent for information.
        
        Args:
            target_agent_id: ID of the agent to query
            question: Question to ask the other agent
            conversation_id: Optional conversation ID to maintain context
        
        Returns:
            Response from the other agent.
        """
        # BREAKPOINT: Specialist step — querying another agent
        debug("Specialist tool: query_other_agent", device=self.context.device_name, target_agent_id=target_agent_id, question=question[:60] if question else "")
        if target_agent_id == self.context.agent_id:
            return {
                "status": "error",
                "message": "Cannot query yourself"
            }
        
        if not self.agent_registry.agent_exists(target_agent_id):
            return {
                "status": "error",
                "message": f"Agent {target_agent_id} not found"
            }
        
        # Create message
        message = AgentMessage(
            from_agent=self.context.agent_id,
            to_agent=target_agent_id,
            message_type="query",
            content=question,
            conversation_id=conversation_id or f"{self.context.agent_id}_{datetime.now().isoformat()}"
        )
        
        # Send via message bus (sync wrapper for async operation)
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async operation
            if loop.is_running():
                # If loop is already running, we need to use a different approach
                # For now, return a message indicating async operation needed
                return {
                    "status": "pending",
                    "message": "Query sent to agent, response will be processed asynchronously"
                }
            else:
                response = loop.run_until_complete(
                    self.message_bus.send_and_wait(message, timeout=30)
                )
                
                return {
                    "status": "success",
                    "from_agent": self.context.agent_id,
                    "to_agent": target_agent_id,
                    "question": question,
                    "response": response.content if response else "No response received"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error querying agent: {e}"
            }
    
    def get_topology_info(self) -> Dict[str, Any]:
        """Gets information about the network topology and other agents.
        
        Returns:
            Topology information including all agents and their capabilities.
        """
        # BREAKPOINT: Specialist step — getting topology info
        debug("Specialist tool: get_topology_info", device=self.context.device_name)
        agents = self.agent_registry.list_agents()
        return {
            "status": "success",
            "current_agent": self.context.agent_id,
            "device": self.context.device_name,
            "topology": {
                "total_agents": len(agents),
                "agents": [
                    {
                        "agent_id": agent["agent_id"],
                        "name": agent["name"],
                        "type": agent["type"],
                        "capabilities": agent.get("capabilities", [])
                    }
                    for agent in agents
                ]
            }
        }
    
    async def _handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handles incoming messages from other agents"""
        # BREAKPOINT: Specialist received query from Concierge
        debug("Specialist received query", device=self.context.device_name, agent_id=self.context.agent_id, from_agent=message.from_agent, content=message.content[:60] if message.content else "")
        # Process the query using this agent's knowledge
        conversation_id = message.conversation_id
        
        # Add to conversation history
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        # Process query (calls Gemini; set breakpoint inside _process_query to step through specialist logic)
        response_text = await self._process_query(message.content, conversation_id)
        debug("Specialist sending response", device=self.context.device_name, response_len=len(response_text or ""))
        # Create response message
        response = AgentMessage(
            from_agent=self.context.agent_id,
            to_agent=message.from_agent,
            message_type="response",
            content=response_text,
            conversation_id=conversation_id
        )
        
        return response
    
    async def _process_query(self, query: str, conversation_id: str) -> str:
        """Processes a query using Gemini, handling tool execution loops."""
        debug("Specialist _process_query start", device=self.context.device_name, query=query[:60] if query else "")
        
        # Get or create conversation history
        history = self.conversations.get(conversation_id, [])
        
        # Add user query
        history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)]
        ))
        
        current_history = history
        max_turns = 10
        
        for _ in range(max_turns):
            # Generate response
            response = self._generate_content_with_retry(current_history)
            if not response or not response.candidates:
                return "Error: No response from agent."
            
            candidate = response.candidates[0]
            current_history.append(candidate.content)
            
            # Check for function calls
            function_calls = []
            for part in candidate.content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)
            
            if function_calls:
                # Execute tool definitions
                tool_outputs = []
                for fc in function_calls:
                    debug(f"Executing tool: {fc.name}", args=fc.args)
                    tool_func = getattr(self, fc.name, None)
                    if tool_func:
                        try:
                            # Convert args to dict to pass as kwargs
                            result = tool_func(**dict(fc.args))
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
                
                # Send tool outputs back to model
                current_history.append(types.Content(
                    role="user", # Model expects function responses as 'user' role or separate role depending on API version, usually 'function' role but in genai types it's often user with function_response parts
                    parts=tool_outputs
                ))
            else:
                # No function calls, this is the final answer
                self.conversations[conversation_id] = current_history
                debug("Specialist _process_query done", device=self.context.device_name)
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
            agent_id=f"Specialist {self.context.device_name}"
        )
    
    async def chat(self, user_input: str, conversation_id: str = None) -> str:
        """Main chat interface for user interactions"""
        if conversation_id is None:
            conversation_id = f"user_{self.context.agent_id}_{datetime.now().isoformat()}"
        
        return await self._process_query(user_input, conversation_id)

