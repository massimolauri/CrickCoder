import platform
from typing import Optional
from agno.agent import Agent
from agno.compression.manager import CompressionManager
from src.core.config.factory_models import build_model_for_runtime
from src.core.config.model_limits import get_token_limit_for_model
from src.core.storage.knowledge import get_shared_knowledge
from src.core.storage.storage import get_agent_storage
from src.prompts.loader import load_prompt
from src.models import LLMSettings

# Import Tools
from src.tools.crick_brain_tools import CrickBrainTools
from src.tools.crickcoder_file_tools import CrickCoderFileTools
from src.tools.crickcoder_shell_tools import CrickCoderShellTools
from src.tools.crickcoder_template_tools import CrickCoderTemplateTools
from pathlib import Path

def build_coder(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None, selected_theme_id: Optional[str] = None):
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
    
    # Base tools list
    tools_list = [brain_tool, file_tools, shell_tools]

    # Conditional Template Tools
    if selected_theme_id:
        template_tools = CrickCoderTemplateTools(project_root=project_root, llm_settings=llm_settings)
        tools_list.append(template_tools)

    # 4. Build Model
    model = build_model_for_runtime(
        provider=llm_settings.provider,
        model_id=llm_settings.model_id,
        temperature=llm_settings.temperature,
        api_key=llm_settings.api_key,
        base_url=llm_settings.base_url
    )

    # 5. Create Agent
    return Agent(
        name="Coder",
        role="Senior Developer",
        model=model,
        # Compression Manager
        compression_manager=CompressionManager(
            model=model,
            compress_tool_results=False,
            compress_token_limit=get_token_limit_for_model(llm_settings.model_id, llm_settings.compression_threshold)
        ),
        # Shared Knowledge
        knowledge=get_shared_knowledge(project_root),
        search_knowledge=True, 
        
        # Tools List
        tools=tools_list,
        
        # Instructions
        instructions=[
            load_prompt("coder.md", model_id=llm_settings.model_id),
            os_context,
            "Follow the Strict Workflow: Orientation -> Planning -> Execution -> Reporting."
        ],
        
        # Storage & Session
        db=storage,
        session_id=session_id,
        add_history_to_context=True, 
        num_history_runs=5,
        
        debug_mode=True,
        markdown=True
    )