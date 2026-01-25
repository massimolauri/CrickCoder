
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import CrickCoderTemplateTools...")
    from src.tools.crickcoder_template_tools import CrickCoderTemplateTools
    print("Import successful.")

    print("Attempting instantiation...")
    # We can pass None/Mock for dependencies since we just want to check syntax/init logic
    tools = CrickCoderTemplateTools(project_root=os.getcwd())
    print("Instantiation successful.")
    
    # Check if methods exist and signature is correct (by inspecting or mock calling)
    if not hasattr(tools, 'install_template'):
        raise Exception("Method 'install_template' missing!")
    
    # Inspect signature
    import inspect
    sig = inspect.signature(tools.install_template)
    if 'target_path' not in sig.parameters:
        raise Exception("Method 'install_template' missing 'target_path' parameter!")
        
    print("Verification passed: Module is valid, class instantiates, and signature matches.")

except Exception as e:
    print(f"VERIFICATION FAILED: {e}")
    sys.exit(1)
