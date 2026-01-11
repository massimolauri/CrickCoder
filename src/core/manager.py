import logging
import os
from typing import AsyncGenerator, Optional, Any, List, Dict
from agno.agent import Agent
from src.agents.factory import build_agents
from src.models import LLMSettings

# --- Setup Logging ---
logger = logging.getLogger(__name__)

class VibingManager:
    """
    Central Controller (Facade). 
    Directly routes requests to specific agents (CODER, ARCHITECT, etc.)
    without an intermediary Orchestrator or Team Leader.
    """

    def __init__(self, session_id: str, project_root: str, auto_approval: bool = True, llm_settings: Optional[LLMSettings] = None):
        self.session_id = session_id
        self.project_root = project_root

        # 1. Build specialized Agents via Factory
        # The factory returns a map: {"CODER": coder_obj, "ARCHITECT": arch_obj}
        # auto_approval is now True by default as per your new architecture
        self.agents_map: Dict[str, Agent] = build_agents(project_root, session_id, auto_approval, llm_settings)

    async def arun(
        self, 
        message: str, 
        agent_id: str,  # Directly identified by the frontend
        stream: bool = True, 
        stream_events: bool = True,
        yield_run_output: bool = True,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """
        Routes the user message directly to the specified agent.
        """
        
        # 1. Select the specific agent from the map
        # agent_id corresponds to the key in the factory (e.g., "CODER")
        active_agent = self.agents_map.get(agent_id.upper())
        
        if not active_agent:
            error_msg = f"Agent '{agent_id}' not found in current project context."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        logger.info(f"🚀 Routing request to: {agent_id} | Session: {self.session_id}")

        # 2. Proxy Execution Stream
        # Directly call the agent's arun method
        async for event in active_agent.arun(
            message,
            stream=stream,
            stream_events=stream_events,
            yield_run_output=yield_run_output,
            **kwargs
        ):
            # Ensure the agent_name is injected for UI consistency 
            if hasattr(event, "agent_name") and not event.agent_name:
                event.agent_name = active_agent.name
            
            yield event
