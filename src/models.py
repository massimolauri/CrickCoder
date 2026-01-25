from typing import Literal, Optional
from pydantic import BaseModel, Field

# --- ROUTER MODELS (Internal Logic) ---

class RoutingDecision(BaseModel):
    """Structured output for the Semantic Router."""
    chain_of_thought: str = Field(
        ..., 
        description="Step-by-step reasoning for the decision."
    )
    next_speaker: Literal["ARCHITECT", "CODER", "PLANNER", "CHAT"] = Field(
        ..., 
        description="The agent assigned to the next turn."
    )
    instruction: Optional[str] = Field(
        None, 
        description="Specific context or instruction to inject into the next agent's prompt."
    )

# --- API MODELS (External Interface) ---

class LLMSettings(BaseModel):
    """LLM configuration settings."""
    provider: str
    model_id: str
    api_key: str
    temperature: float = 0.2
    compression_threshold: Optional[int] = None
    base_url: Optional[str] = None

class ChatRequest(BaseModel):
    """Payload for starting a new chat turn."""
    message: str
    project_path: str
    agent_id: Literal["ARCHITECT", "CODER", "PLANNER"]
    session_id: Optional[str] = None
    # If True, Coder executes immediately (God Mode).
    # If False, Coder pauses on file/shell operations (Safe Mode).
    auto_approval: bool = False
    llm_settings: Optional[LLMSettings] = None 
    selected_theme_id: Optional[str] = None

class ContinueRequest(BaseModel):
    """Payload for resuming a paused run (HITL)."""
    run_id: str
    session_id: str
    project_path: str
    decision: Literal["approve", "reject"]
    feedback: Optional[str] = None