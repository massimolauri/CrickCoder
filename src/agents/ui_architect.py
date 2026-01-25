import platform
from typing import Optional, List
from pydantic import BaseModel, Field
from agno.agent import Agent
from src.core.factory_models import build_model_for_runtime
from src.core.knowledge import get_shared_knowledge
from src.core.storage import get_agent_storage
from src.prompts.loader import load_prompt
from src.models import LLMSettings

# --- Pydantic Models for Structured Output ---
class UIComponent(BaseModel):
    name: str = Field(..., description="Technical Name (e.g. 'Transactions Data Table')")
    category: str = Field(..., description="Concise UI Classification (e.g. 'Table', 'Modal', 'Navigation', 'Card', 'Form', 'Layout')")
    selector: str = Field(..., description="Unique CSS Selector string (e.g. '#transactions-table-wrapper')")
    description: str = Field(..., description="Detailed semantic description for vector search. Describe purpose, visual style, and content.")
    dependencies: List[str] = Field(default_factory=list, description="List of specific asset files (CSS/JS) required by this component. Exclude global theme files.")
    requires_js: bool = Field(False, description="Does this component require JavaScript logic?")

class AnalysisResult(BaseModel):
    components: List[UIComponent] = Field(..., description="List of identified independent UI components")

def build_ui_architect(project_root: str, session_id: str, auto_approval: bool = False, llm_settings: Optional[LLMSettings] = None):
    """
    Costruisce l'agente UI Architect per l'analisi dei template.

    Args:
        project_root: Path assoluto del progetto.
        session_id: ID sessione.
        auto_approval: Flag per God Mode (non strettamente usato qui, ma mantenuto per consistenza).
        llm_settings: Configurazione LLM opzionale.
    """
    
    # 1. Context OS
    current_os = platform.system()
    os_context = f"SYSTEM OS: {current_os}."


    # 3. Configurazione Modello LLM
    if not llm_settings:
        raise ValueError("llm_settings è obbligatorio per costruire l'agente UI Architect")

    model = build_model_for_runtime(
        provider=llm_settings.provider,
        model_id=llm_settings.model_id,
        temperature=llm_settings.temperature,
        api_key=llm_settings.api_key,
        base_url=llm_settings.base_url
    )

    return Agent(
        name="UIArchitect",
        role="UI Component Architect",
        model=model,
        output_schema=AnalysisResult, 
        instructions=[
            load_prompt("ui_architect.md"),
            os_context
        ],
        markdown=True,
        debug_mode=True
    )
