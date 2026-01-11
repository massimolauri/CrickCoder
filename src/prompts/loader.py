"""
Prompt loading utilities for Crick.
"""
import os


def load_prompt(filename: str) -> str:
    """
    Load a prompt file from the prompts directory.

    Args:
        filename: Name of the prompt file (e.g., "architect.md")

    Returns:
        Content of the prompt file as string.
    """
    # prompts directory is the same as this module's directory
    prompts_dir = os.path.dirname(__file__)
    filepath = os.path.join(prompts_dir, filename)

    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()