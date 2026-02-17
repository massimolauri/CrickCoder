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
from src.tools.crickcoder_template_tools import CrickCoderTemplateTools

from src.tools.crick_brain_tools import CrickBrainTools

def build_planner(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None, selected_theme_id: Optional[str] = None):
    """
    Costruisce l'agente Planner.
    Identico all'Architect come configurazione, ma usa 'planner.md' e ha un ruolo diverso.
    """
    storage = get_agent_storage(project_root=project_root) 
    
    current_os = platform.system()
    os_context = f"SYSTEM CONTEXT: Host OS is {current_os}."

    instructions_list = [
            load_prompt("planner.md", model_id=llm_settings.model_id),
            os_context
        ]

    if not llm_settings:
        raise ValueError("llm_settings e' obbligatorio per costruire l'agente Planner")

    model = build_model_for_runtime(
        provider=llm_settings.provider,
        model_id=llm_settings.model_id,
        temperature=llm_settings.temperature,
        api_key=llm_settings.api_key,
        base_url=llm_settings.base_url
    )
    
    # Base tools
    tools_list = [
        CrickBrainTools(project_root=project_root, llm_settings=llm_settings, session_id=session_id)
    ]
    
    # Conditional Template Tools
    # Template Tools (Always available)
    tools_list.append(CrickCoderTemplateTools(project_root=project_root, llm_settings=llm_settings))

    return Agent(
        name="Planner",
        role="Technical Lead",
        model=model,
        # Compression Manager to save context
        compression_manager=CompressionManager(
            model=model,
            compress_tool_results=False, 
            compress_token_limit=get_token_limit_for_model(llm_settings.model_id, llm_settings.compression_threshold)
        ),
        knowledge=get_shared_knowledge(project_root),
        search_knowledge=True,
        db=storage,
        user_id="crickdeveloper",
        session_id=session_id,
        enable_session_summaries=True,
        instructions=instructions_list,
        markdown=True,
        debug_mode=True,
        add_history_to_context=True,
        num_history_runs=5,
        tools=tools_list
    )
