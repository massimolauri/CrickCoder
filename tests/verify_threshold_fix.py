
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.models import LLMSettings
from src.core.model_limits import get_token_limit_for_model

def test_threshold_logic():
    print("Testing Threshold Logic...")

    # Case 1: Default (No threshold provided)
    print("\nCase 1: No compression_threshold provided")
    settings_default = LLMSettings(
        provider="openai",
        model_id="deepseek-chat",
        api_key="sk-..."
    )
    print(f"Settings.compression_threshold: {settings_default.compression_threshold}")
    
    limit = get_token_limit_for_model(settings_default.model_id, settings_default.compression_threshold)
    print(f"Calculated Limit for 'deepseek-chat': {limit}")
    
    if limit != 84000:
        print(f"FAIL: Expected 84000, got {limit}")
        return False
        
    # Case 2: Explicit Threshold
    print("\nCase 2: Explicit compression_threshold=1000")
    settings_custom = LLMSettings(
        provider="openai",
        model_id="deepseek-chat",
        api_key="sk-...",
        compression_threshold=1000
    )
    print(f"Settings.compression_threshold: {settings_custom.compression_threshold}")
    
    limit_custom = get_token_limit_for_model(settings_custom.model_id, settings_custom.compression_threshold)
    print(f"Calculated Limit: {limit_custom}")
    
    if limit_custom != 1000:
        print(f"FAIL: Expected 1000, got {limit_custom}")
        return False

    print("\nSUCCESS: Logic is correct.")
    return True

if __name__ == "__main__":
    if not test_threshold_logic():
        sys.exit(1)
