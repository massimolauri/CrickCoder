from typing import Dict, Optional, Any
from agno.agent import Agent
from src.models import LLMSettings

# Importiamo le funzioni dai nuovi file specifici
from src.agents.coder import build_coder
from src.agents.planner import build_planner

def build_agents(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None, selected_theme_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Factory principale che assembla il team.

    Args:
        project_root: Root del progetto utente.
        session_id: ID Sessione condivisa.
        auto_approval: Flag per God Mode (True) o Safe Mode (False).
        llm_settings: Configurazione LLM opzionale.
        selected_theme_id: ID del tema selezionato (se presente).
    """

    # 1. Costruisci Coder
    coder = build_coder(project_root, session_id, auto_approval, llm_settings, selected_theme_id)

    # 2. Costruisci Planner
    planner = build_planner(project_root, session_id, auto_approval, llm_settings, selected_theme_id)

    # 3. Restituisci la mappa
    return {
        "CODER": coder,
        "PLANNER": planner
    }