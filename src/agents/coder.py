import platform
from typing import Optional
from agno.agent import Agent
from src.core.factory_models import build_model_for_runtime
from src.core.knowledge import get_shared_knowledge
from src.core.storage import get_agent_storage
from src.prompts.loader import load_prompt
from src.models import LLMSettings

# Import Tools
from src.tools.crick_brain_tools import CrickBrainTools
from src.tools.crickcoder_file_tools import CrickCoderFileTools
from src.tools.crickcoder_shell_tools import CrickCoderShellTools
from src.tools.crickcoder_template_tools import CrickCoderTemplateTools
from pathlib import Path

def build_coder(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None):
    """
    Builds the Coder Agent (Single Agent with Tools).
    """
    
    # 1. Context OS (Imperative)
    current_os = platform.system()
    os_release = platform.release()
    os_context = f"SYSTEM OS: {current_os} ({os_release})."

    storage = get_agent_storage(project_root=project_root) 
    
    # 2. Safety Configuration
    enable_tool_confirmation = not auto_approval

    if not llm_settings:
        raise ValueError("llm_settings is required to build the Coder agent")

    # 3. Instantiate Tools
    brain_tool = CrickBrainTools(project_root=project_root, llm_settings=llm_settings, session_id=session_id)
    
    file_tools = CrickCoderFileTools(
        base_dir=Path(project_root),
        enable_confirmation=enable_tool_confirmation
    )
    
    shell_tools = CrickCoderShellTools(
        base_dir=Path(project_root),
        timeout_seconds=120,
        enable_confirmation=enable_tool_confirmation
    )
    
    template_tools = CrickCoderTemplateTools(project_root=project_root)

    # 4. Build Model
    model = build_model_for_runtime(
        provider=llm_settings.provider,
        model_id=llm_settings.model_id,
        temperature=llm_settings.temperature,
        api_key=llm_settings.api_key
    )

    # 5. Create Agent
    return Agent(
        name="Coder",
        role="Senior Developer",
        model=model,
        # Shared Knowledge
        knowledge=get_shared_knowledge(project_root),
        search_knowledge=True, 
        
        # Tools List
        tools=[brain_tool, file_tools, shell_tools, template_tools],
        
        # Instructions
        instructions=[
            load_prompt("coder.md"),
            os_context,
            "Follow the Strict Workflow: Orientation -> Planning -> Execution -> Reporting."
        ],
        
        # Storage & Session
        db=storage,
        session_id=session_id,
        add_history_to_context=True, 
        num_history_runs=10,
        
        debug_mode=True,
        markdown=True
    )