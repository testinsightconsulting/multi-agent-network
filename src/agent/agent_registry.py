"""Agent registry for discovery and routing"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import threading


@dataclass
class AgentInfo:
    """Information about a registered agent"""
    agent_id: str
    name: str
    agent_type: str
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class AgentRegistry:
    """Registry for all agents in the system"""
    
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = threading.Lock()
    
    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: str,
        capabilities: List[str] = None,
        metadata: Dict = None
    ):
        """Register an agent"""
        with self._lock:
            self._agents[agent_id] = AgentInfo(
                agent_id=agent_id,
                name=agent_name,
                agent_type=agent_type,
                capabilities=capabilities or [],
                metadata=metadata or {}
            )
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        with self._lock:
            self._agents.pop(agent_id, None)
    
    def agent_exists(self, agent_id: str) -> bool:
        """Check if agent exists"""
        with self._lock:
            return agent_id in self._agents
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information"""
        with self._lock:
            return self._agents.get(agent_id)
    
    def list_agents(self) -> List[Dict]:
        """List all registered agents"""
        with self._lock:
            return [
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "type": agent.agent_type,
                    "capabilities": agent.capabilities,
                    "metadata": agent.metadata
                }
                for agent in self._agents.values()
            ]
    
    def find_agents_by_capability(self, capability: str) -> List[str]:
        """Find agents with a specific capability"""
        with self._lock:
            return [
                agent.agent_id
                for agent in self._agents.values()
                if capability in agent.capabilities
            ]

