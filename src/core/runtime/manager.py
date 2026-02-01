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

    def __init__(self, session_id: str, project_root: str, auto_approval: bool = True, llm_settings: Optional[LLMSettings] = None, selected_theme_id: Optional[str] = None):
        self.session_id = session_id
        self.project_root = project_root

        # 1. Build specialized Agents via Factory
        # The factory returns a map: {"CODER": coder_obj, "ARCHITECT": arch_obj}
        # auto_approval is now True by default as per your new architecture
        self.agents_map: Dict[str, Agent] = build_agents(project_root, session_id, auto_approval, llm_settings, selected_theme_id)

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
            logger.error(f"{error_msg}")
            raise ValueError(error_msg)

        logger.info(f"Routing request to: {agent_id} | Session: {self.session_id}")

        # --- 0. Context Injection (Shadow Workspace) ---
        from src.core.runtime.shadow_workspace import ShadowWorkspace
        # We need a stable run_id for this turn to track changes.
        # If kwargs has run_id use it, else generate (though typically run_id is internal to Agent)
        # Ideally we want the SAME run_id that the agent receives.
        # Since Agno generates run_id internally if not passed, we might be out of sync if we generate one here.
        # HOWEVER, we can simple trigger the context with a "Turn ID".
        # Let's generate a unique ID for this 'Action Turn' which suffices for the Undo feature.
        import uuid
        current_run_context_id = str(uuid.uuid4())
        
        ShadowWorkspace.get_instance().set_context(
            project_root=self.project_root,
            session_id=self.session_id,
            run_id=current_run_context_id
        )

        # --- Context Injection: Read Task List from Brain ---
        # This ensures the agent is aware of the current project status even in new sessions.
        try:
             brain_task_path = os.path.join(self.project_root, ".crick", "sessions", self.session_id, "brain", "task.md")
             if os.path.exists(brain_task_path):
                 with open(brain_task_path, "r", encoding="utf-8") as f:
                     task_content = f.read()
                 
                 # Prepend context to the message
                 # We use a clear separator so the agent knows this is context, not user speech.
                 context_header = (
                     "\n\n--- [SYSTEM] SYSTEM CONTEXT: CURRENT PROJECT TASKS ---\n"
                     f"{task_content}\n"
                     "--- END CONTEXT ---\n\n"
                 )
                 message = context_header + message
        except Exception as e:
            logger.warning(f"Failed to inject task context: {e}")

        # 2. Proxy Execution Stream
        # Yield metadata event locally first
        yield {
            "type": "meta",
            "shadow_run_id": current_run_context_id,
            "agent": agent_id
        }

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
            
            # Inject shadow_run_id into RunResponse objects if possible, for correlation
            if hasattr(event, "shadow_run_id"):
                 pass # Already set?
            else:
                 # We can't easily monkeypatch internal Pydantic models of Agno on the fly without risk.
                 # Rely on the initial "meta" event for the UI to track the ID.
                 pass

            yield event
