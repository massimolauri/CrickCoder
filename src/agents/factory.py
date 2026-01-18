from typing import Dict, Optional
from agno.agent import Agent
from src.models import LLMSettings

# Importiamo le funzioni dai nuovi file specifici
from src.agents.architect import build_architect
from src.agents.coder import build_coder
from src.agents.planner import build_planner

def build_agents(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None) -> Dict[str, Agent]:
    """
    Factory principale che assembla il team.

    Args:
        project_root: Root del progetto utente.
        session_id: ID Sessione condivisa.
        auto_approval: Flag per God Mode (True) o Safe Mode (False).
        llm_settings: Configurazione LLM opzionale.
    """

    # 1. Costruisci Architect
    architect = build_architect(project_root, session_id, auto_approval, llm_settings)

    # 2. Costruisci Coder
    coder = build_coder(project_root, session_id, auto_approval, llm_settings)

    # 3. Costruisci Planner
    planner = build_planner(project_root, session_id, auto_approval, llm_settings)

    # 4. Restituisci la mappa
    return {
        "ARCHITECT": architect,
        "CODER": coder,
        "PLANNER": planner
    }