
from typing import Optional

# =============================================================================
# MODEL TOKEN LIMITS CONFIGURATION
# =============================================================================
# Edit this dictionary to define the optimal compression threshold for each model.
# The value represents the number of tokens to reserve for tool outputs before
# compression triggers.
#
# Guidelines:
# - Standard Context (8k-32k): 4000-6000
# - Large Context (128k+): 10000-20000 (Prevents "lost in the middle")
# =============================================================================

MODEL_LIMITS = {
    "deepseek-chat": 84000,
    "glm-4.6": 84000,
    "glm-4.7": 84000
}

DEFAULT_LIMIT = 32000

def get_token_limit_for_model(model_id: str, custom_limit: Optional[int] = None) -> int:
    """
    Returns the compression token limit for a given model.
    Prioritizes:
    1. Explicit custom_limit (if provided and > 0)
    2. Known limit in MODEL_LIMITS
    3. DEFAULT_LIMIT
    """
    if custom_limit and custom_limit > 0:
        return custom_limit
        
    return MODEL_LIMITS.get(model_id, DEFAULT_LIMIT)
