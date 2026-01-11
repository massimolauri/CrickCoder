import platform
from pathlib import Path
from typing import Optional
from agno.agent import Agent
from src.core.factory_models import build_model_for_runtime
from src.tools.crickcoder_file_tools import CrickCoderFileTools
from src.tools.crickcoder_shell_tools import CrickCoderShellTools
from src.core.knowledge import get_shared_knowledge
from src.core.storage import get_agent_storage
from src.prompts.loader import load_prompt
from src.models import LLMSettings

def build_coder(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None):
    """
    Costruisce il Coder configurando i tools e la modalità di sicurezza nativa.

    Args:
        project_root: Path assoluto del progetto.
        session_id: ID sessione.
        auto_approval:
            - True (God Mode): Esegue comandi immediatamente.
            - False (Safe Mode): Attiva 'requires_confirmation' nei Tool e mette in pausa Agno.
        llm_settings: Configurazione LLM opzionale.
    """
    
    # 1. Context OS (Imperativo)
    current_os = platform.system()
    os_release = platform.release()
    os_context = f"SYSTEM OS: {current_os} ({os_release}). Use native shell syntax for this OS."


    storage = get_agent_storage(project_root=project_root) 
    # 2. Configurazione Modalità (Logica Nativa Agno)
    # Calcoliamo se i tool devono richiedere conferma
    enable_tool_confirmation = not auto_approval

    # 3. Setup Tools con Path Assoluti e Configurazione Sicurezza
    project_path = Path(project_root)
    
    # FILE TOOLS: Attiviamo la conferma se siamo in Safe Mode
    file_tool = CrickCoderFileTools(
        base_dir=project_path,
        enable_confirmation=enable_tool_confirmation 
    )

    # SHELL TOOLS: Attiviamo la conferma se siamo in Safe Mode
    shell_tool = CrickCoderShellTools(
        base_dir=project_path, 
        timeout_seconds=120,
        enable_confirmation=enable_tool_confirmation 
    )

    # Configurazione Modello LLM
    if not llm_settings:
        raise ValueError("llm_settings è obbligatorio per costruire l'agente Coder")

    model = build_model_for_runtime(
        provider=llm_settings.provider,
        model_id=llm_settings.model_id,
        temperature=llm_settings.temperature,
        api_key=llm_settings.api_key
    )

    return Agent(
        name="Coder",
        role="Senior Developer",
        model=model,
        knowledge=get_shared_knowledge(project_root),
        search_knowledge=True,
        db=storage,
        session_id=session_id,
        user_id="crickdeveloper",
        enable_session_summaries=True,
        tools=[
            file_tool,
            shell_tool
        ],
        instructions=[
            load_prompt("coder.md"),
            os_context
        ],
        markdown=True,
        debug_mode=True,
        add_history_to_context=True,
        num_history_runs=5
    )