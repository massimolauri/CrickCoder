import logging
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from src.core.storage import get_agent_storage

# --- Local Imports ---
from src.prompts.loader import load_prompt
from src.models import RoutingDecision

logger = logging.getLogger(__name__)

async def get_routing_decision(
    user_input: str, 
    session_id: str, 
    user_id:str,
    project_root
) -> RoutingDecision:
    """
    Decides the next step by analyzing the full conversation history directly from storage.
    
    Args:
        user_input: The latest message from the user.
        session_id: The current session ID to read history from.
        storage: The shared database object.
        
    Returns:
        RoutingDecision: Structured object (next_speaker, reasoning, instructions).
    """
    storage = get_agent_storage(project_root=project_root) 
    # We instantiate a temporary 'Reader Agent' for this specific decision.
    # This allows it to see the exact same context as the Architect/Coder.
    orchestrator = Agent(
        name="Orchestrator",
        model=DeepSeek(id="deepseek-chat", temperature=0.1),
        
        # Load the strict State Machine prompt
        instructions=load_prompt("orchestrator.md"),
        
        # Enforce structured output via Pydantic
        output_schema=RoutingDecision, 
        
        # --- STATEFUL MAGIC ---
        db=storage,           # Connect to the shared DB
        session_id=session_id,     # Target the current chat session
        add_history_to_context=True, # READ history automatically
        num_history_runs=5,        # Read last 5 interactions for context
        user_id="crickdeveloper",
        
        # --- SILENT OBSERVER ---
        # Critical: We do NOT want to save the Orchestrator's thoughts 
        # into the chat history, or it will confuse the other agents.
        store_history_messages=False
       
    )

    try:
        # We append the user's latest input manually to the prompt because
        # since we are strictly 'reading' history, this new message 
        # might not be in the DB yet depending on when you call this.
        # (Assuming the Manager calls this BEFORE adding user msg to DB).
        prompt = f"User Input: {user_input}"
        
        response = await orchestrator.arun(prompt)
        return response.content
        
    except Exception as e:
        logger.error(f"Orchestrator failed: {e}")
        # Fail-safe fallback to Architect (Safest bet)
        return RoutingDecision(
            chain_of_thought=f"Orchestrator Error: {e}",
            next_speaker="ARCHITECT",
            instruction="System error in routing. Defaulting to Architect for assistance."
        )