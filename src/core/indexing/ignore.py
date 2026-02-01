"""
Gestione delle regole di ignore (.crickignore).
"""
import os
from typing import Tuple, Set


def load_crickignore_rules(project_root: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Carica le regole di ignore dal file .crickignore.

    Args:
        project_root: Root del progetto (obbligatorio).

    Returns:
        Tuple di (ignore_dirs, ignore_exts, ignore_patterns).
    """
    crickignore_path = os.path.join(project_root, ".crick", ".crickignore")
    if not os.path.exists(crickignore_path):
        return set(), set(), set()

    ignore_dirs = set()
    ignore_exts = set()
    ignore_patterns = set()  # Pattern completi (es. ".crick/")

    with open(crickignore_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Salta commenti e linee vuote
            if not line or line.startswith('#'):
                continue

            # Aggiungi il pattern originale
            ignore_patterns.add(line)

            # Rimuove il trailing slash per le directory
            if line.endswith('/'):
                dir_name = line.rstrip('/')
                ignore_dirs.add(dir_name)
            # Estensioni di file (es. *.pyc)
            elif line.startswith('*.'):
                ext = line[1:]  # Rimuove l'asterisco
                ignore_exts.add(ext)
            # Nomi di file specifici
            elif '.' in line and not line.startswith('.'):
                # Potrebbe essere un file specifico
                ignore_exts.add(f".{line.split('.')[-1]}")
            elif line.startswith('.'):
                ignore_dirs.add(line)

    return ignore_dirs, ignore_exts, ignore_patterns