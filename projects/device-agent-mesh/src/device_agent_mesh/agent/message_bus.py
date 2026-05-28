"""Message bus for inter-agent communication"""
import asyncio
from typing import Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid

try:
    from device_agent_mesh.utils.debug_helper import debug
except ImportError:
    def debug(msg: str, **kwargs: object) -> None: pass  # no-op if utils not on path


@dataclass
class AgentMessage:
    """Message between agents"""
    from_agent: str
    to_agent: str
    message_type: str  # 'query', 'response', 'notification'
    content: str
    conversation_id: str
    message_id: str = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now()


class MessageBus:
    """Handles inter-agent communication"""
    
    def __init__(self):
        self.subscribers: Dict[str, Callable] = {}
        self.pending_responses: Dict[str, asyncio.Future] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
    
    def subscribe(self, agent_id: str, handler: Callable):
        """Subscribe an agent to receive messages"""
        self.subscribers[agent_id] = handler
    
    def unsubscribe(self, agent_id: str):
        """Unsubscribe an agent"""
        if agent_id in self.subscribers:
            del self.subscribers[agent_id]
    
    async def send(self, message: AgentMessage):
        """Send a message asynchronously (fire and forget)"""
        await self.message_queue.put(message)
    
    async def send_and_wait(self, message: AgentMessage, timeout: float = 30.0) -> Optional[AgentMessage]:
        """Send a message and wait for response"""
        future = asyncio.Future()
        self.pending_responses[message.message_id] = future
        
        await self.send(message)
        
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self.pending_responses.pop(message.message_id, None)
            return None
        finally:
            self.pending_responses.pop(message.message_id, None)
    
    async def _process_messages(self):
        """Background task to process messages"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Route to subscriber
                if message.to_agent in self.subscribers:
                    # BREAKPOINT: MessageBus routing query to specialist
                    debug("MessageBus routing to specialist", from_agent=message.from_agent, to_agent=message.to_agent, content=message.content[:60] if message.content else "")
                    handler = self.subscribers[message.to_agent]
                    response = await handler(message)
                    debug("MessageBus specialist responded", to_agent=message.to_agent, has_response=response is not None)
                    # If it's a query and we got a response, resolve the future
                    if message.message_type == "query" and response:
                        if message.message_id in self.pending_responses:
                            self.pending_responses[message.message_id].set_result(response)
                else:
                    print(f"Warning: No subscriber for agent {message.to_agent}")
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
    
    async def start(self):
        """Start the message bus"""
        self._running = True
        asyncio.create_task(self._process_messages())
    
    async def stop(self):
        """Stop the message bus"""
        self._running = False

