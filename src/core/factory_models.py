import logging
from typing import Any, Dict, Type, Optional

# Agno Model Imports
from agno.models.openai import OpenAIChat, OpenAILike
from agno.models.deepseek import DeepSeek
from agno.models.google import Gemini
from agno.models.nvidia import Nvidia
from agno.models.ollama import Ollama
from agno.models.openrouter import OpenRouter
from agno.models.anthropic import Claude

logger = logging.getLogger(__name__)

# Registry for dynamic instantiation
MODEL_REGISTRY: Dict[str, Type] = {
    "deepseek": DeepSeek,
    "openailike": OpenAILike,
    "openai": OpenAIChat,
    "gemini": Gemini,
    "nvidia": Nvidia,
    "ollama": Ollama,
    "openrouter": OpenRouter,
    "claude": Claude
}

# Alias mapping for frontend compatibility
PROVIDER_ALIASES = {
    "openaichat": "openai",
    "openai": "openai",
    "openailike": "openailike",
    "deepseek": "deepseek",
    "gemini": "gemini",
    "nvidia": "nvidia",
    "ollama": "ollama",
    "openrouter": "openrouter",
    "claude": "claude",
    "openai-like": "openailike",
    "openai_chat": "openai",
}

def build_model_for_runtime(
    provider: str,
    model_id: str,
    temperature: float,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> Any:
    """
    Creates an Agno model instance with provided credentials and settings.
    If api_key is None, Agno will automatically fallback to environment variables.
    """
    provider_key = provider.lower()
    # Normalize using aliases
    canonical_key = PROVIDER_ALIASES.get(provider_key, provider_key)
    model_class = MODEL_REGISTRY.get(canonical_key)

    if not model_class:
        raise ValueError(f"Unknown provider: {provider}. Supported: {list(MODEL_REGISTRY.keys())}")

    logger.info(f"Building model: {provider_key} | ID: {model_id} | Temp: {temperature} | BaseURL: {base_url}")

    # Configuration dictionary for the constructor
    config = {
        "id": model_id,
        "temperature": temperature
    }

    # Add api_key only if provided (Ollama for example doesn't use it)
    if api_key:
        config["api_key"] = api_key

    # Add base_url if provided (Critical for OpenAI Compatible / Local models)
    if base_url:
        config["base_url"] = base_url

    return model_class(**config)