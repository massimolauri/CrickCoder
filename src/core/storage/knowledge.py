from src.core.storage.storage import TABLE_NAME
from src.core.runtime.project_init import get_db_path
from src.core.indexing.indexer_engine import UniversalCodeIndexer

# Dizionario per memorizzare knowledge base per diversi progetti
_knowledge_instances = {}

def get_shared_knowledge(project_root: str = None):
    """Restituisce la knowledge base per il progetto specificato."""
    if project_root is None:
        # Usa la directory corrente come default
        import os
        project_root = os.getcwd()

    if project_root not in _knowledge_instances:
        print(f"Caricamento Knowledge Base per: {project_root}")
        db_path = get_db_path(project_root)
        indexer = UniversalCodeIndexer(db_path, TABLE_NAME)
        _knowledge_instances[project_root] = indexer.knowledge

    return _knowledge_instances[project_root]