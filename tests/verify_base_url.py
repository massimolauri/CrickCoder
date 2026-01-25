
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

# Mock the MODEL_REGISTRY before importing factory_models
# We need to do this because importing factory_models imports agno which might need api keys or env vars
# But wait, python imports are cached. 
# Better strategy: Import factory_models, then patch MODEL_REGISTRY.

try:
    from src.core import factory_models
    
    # Mock class to capture init args
    class MockModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    # Patch registry
    factory_models.MODEL_REGISTRY["openai"] = MockModel
    
    print("Testing build_model_for_runtime with base_url...")
    
    # Test Call
    model = factory_models.build_model_for_runtime(
        provider="openai",
        model_id="gpt-4",
        temperature=0.5,
        api_key="sk-test",
        base_url="http://localhost:1234/v1"
    )
    
    # Verification
    if hasattr(model, 'kwargs'):
        config = model.kwargs
        print(f"Config received: {config}")
        
        if config.get("base_url") == "http://localhost:1234/v1":
            print("SUCCESS: base_url was passed correctly.")
        else:
            raise Exception(f"FAILURE: base_url missing or incorrect in config: {config}")
            
        if config.get("api_key") == "sk-test":
             print("SUCCESS: api_key was passed correctly.")
        else:
             raise Exception("FAILURE: api_key missing.")
    else:
        raise Exception("Model was not instantiated correctly (not our MockModel).")
        
except Exception as e:
    print(f"VERIFICATION FAILED: {e}")
    sys.exit(1)
