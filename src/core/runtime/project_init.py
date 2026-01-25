"""
Project initialization utilities for Crick.
Creates .crick/knowledge/ directory and .crickignore file.
"""
import os
from typing import Optional

# Import BASE_DIR from the main package
try:
    from src import BASE_DIR
except ImportError:
    # Fallback calculation if src package not properly initialized
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db_path(project_root: Optional[str] = None) -> str:
    """
    Returns the LanceDB database path in the .crick/knowledge/ directory of the project.

    Args:
        project_root: Root path of the user project. If None, uses Crick's own directory.

    Returns:
        Absolute path to the knowledge database directory.
    """
    if project_root is None:
        project_root = BASE_DIR

    # Create path: project/.crick/knowledge/
    crick_dir = os.path.join(project_root, ".crick")
    knowledge_dir = os.path.join(crick_dir, "knowledge")

    # Create directories if they don't exist
    os.makedirs(knowledge_dir, exist_ok=True)

    # Create .crickignore file if it doesn't exist
    crickignore_path = os.path.join(crick_dir, ".crickignore")
    if not os.path.exists(crickignore_path):
        _create_default_crickignore(crickignore_path)

    return knowledge_dir


def _create_default_crickignore(filepath: str) -> None:
    """
    Creates a .crickignore file with default ignore rules.

    Args:
        filepath: Path where to create the .crickignore file.
    """
    # Template path
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # src directory
        "templates",
        ".crickignore.default"
    )

    try:
        with open(template_path, 'r', encoding='utf-8') as tf:
            default_ignore = tf.read()
    except FileNotFoundError:
        # Hardcoded fallback (should never happen)
        default_ignore = """# File e directory da ignorare per Crick
# Questo file segue lo stesso formato di .gitignore

# Directory di sistema
.git/
.crick/           # La cartella di Crick stessa
__pycache__/
.idea/
.vscode/
node_modules/
venv/
target/
build/
dist/
*.egg-info/

# File di build/compilazione
*.pyc
*.pyo
*.pyd
*.so
*.dll
*.class
*.jar

# File di log e temporanei
*.log
*.tmp
*.temp
*.swp
*.swo

# Database e file di dati
*.db
*.sqlite
*.sqlite3
*.lance

# File di ambiente
.env
.env.local
.env.*
*.env

# File di configurazione locale
*.local
*.local.*

#Other
*.svg
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(default_ignore)