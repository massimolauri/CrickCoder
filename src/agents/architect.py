import platform
from typing import Optional
from agno.agent import Agent
from src.core.factory_models import build_model_for_runtime
from src.core.knowledge import get_shared_knowledge
from src.core.storage import get_agent_storage
from src.prompts.loader import load_prompt
from src.models import LLMSettings

def build_architect(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None):
    """
    Costruisce l'agente Architect con consapevolezza della modalità di approvazione.

    Args:
        project_root: Root del progetto.
        session_id: ID sessione.
        auto_approval: Flag per God Mode.
        llm_settings: Configurazione LLM opzionale.
    """
    # 1. Gestione Storage (Se non passato, lo crea)
    storage = get_agent_storage(project_root=project_root) 

    # 2. Context OS
    current_os = platform.system()
    os_release = platform.release()
    os_context = (
        f"SYSTEM CONTEXT: Host OS is {current_os} ({os_release}). "
        "Ensure all planned shell commands are valid for this OS syntax."
    )

    instructions_list = [
            load_prompt("architect.md"),
            os_context
        ]

    # 5. Configurazione Modello LLM
    if not llm_settings:
        raise ValueError("llm_settings è obbligatorio per costruire l'agente Architect")

    model = build_model_for_runtime(
        provider=llm_settings.provider,
        model_id=llm_settings.model_id,
        temperature=llm_settings.temperature,
        api_key=llm_settings.api_key
    )

    # 6. Costruzione Agente
    return Agent(
        name="Architect",
        role="System Architect",
        model=model,
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
        num_history_runs=5
    )