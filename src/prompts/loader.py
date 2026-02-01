"""
Prompt loading utilities for Crick.
"""
import os
import sys

def load_prompt(filename: str, model_id: str = None) -> str:
    """
    Load a prompt file from the prompts directory, with model-specific fallback.
    
    Strategy:
    1. If model_id is provided, try `prompts/<model_family>/<filename>`
       (e.g. 'deepseek-chat' -> 'prompts/deepseek/planner.md')
    2. Fallback to `prompts/<filename>` (Base prompt)

    Args:
        filename: Name of the prompt file (e.g., "planner.md")
        model_id: Optional model identifier (e.g. "deepseek-chat")

    Returns:
        Content of the prompt file as string.
    """
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        # In --onedir mode, assets are usually in _internal/src/prompts if mapped there
        # but sys._MEIPASS usually points to _internal.
        # We mapped 'src/prompts' -> 'src/prompts' in spec, so it should be at _MEIPASS/src/prompts
        if hasattr(sys, '_MEIPASS'):
            prompts_dir = os.path.join(sys._MEIPASS, 'src', 'prompts')
        else:
             # Fallback, though _MEIPASS should exist
             prompts_dir = os.path.join(os.path.dirname(sys.executable), 'src', 'prompts')
    else:
        prompts_dir = os.path.dirname(__file__)
    
    # 1. Try Model-Specific Path
    if model_id:
        # Simple heuristic: "deepseek" in "deepseek-chat" -> "deepseek"
        model_family = None
        if "deepseek" in model_id.lower():
            model_family = "deepseek"
        elif "gpt" in model_id.lower():
            model_family = "openai"
        elif "claude" in model_id.lower():
            model_family = "anthropic"
            
        if model_family:
            specific_path = os.path.join(prompts_dir, model_family, filename)
            if os.path.exists(specific_path):
                with open(specific_path, 'r', encoding='utf-8') as f:
                    return f.read()

    # 2. Fallback to Base Path
    filepath = os.path.join(prompts_dir, filename)
    if not os.path.exists(filepath):
         # If not found in base, raising error might be better, or just return empty string/comment
         # But usually we expect base prompts for generic tools
         raise FileNotFoundError(f"Prompt file not found: {filename} (checked specific and base paths)")

    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()