import os
import sqlite3
import uuid
import time
import logging
from typing import List, Dict, Optional, Any
from agno.db.sqlite import SqliteDb
from agno.db.sqlite import AsyncSqliteDb
from src import BASE_DIR

# LanceDB table name for project vectors
TABLE_NAME = "project_vectors"
from agno.db import SessionType

logger = logging.getLogger(__name__)


def generate_session_id() -> str:
    """
    Genera un ID sessione univoco nel formato: session_<timestamp>_<random>
    Esempio: session_1767184020_abc123
    """
    timestamp = int(time.time())
    random_part = str(uuid.uuid4())[:8]
    return f"session_{timestamp}_{random_part}"

def get_agent_db_path(project_root: str = None) -> str:
    """
    Restituisce il path del database SQLite degli agenti nella cartella .crick/sessions/ del progetto.
    Se project_root è None, usa BASE_DIR (compatibilità con vecchio comportamento).
    """
    if project_root is None:
        project_root = BASE_DIR
        # Vecchio comportamento: storage_data/ nella directory di Crick
        storage_dir = os.path.join(project_root, "storage_data")
    else:
        # Nuovo comportamento: .crick/sessions/ nel progetto target
        crick_dir = os.path.join(project_root, ".crick")
        storage_dir = os.path.join(crick_dir, "sessions")

    os.makedirs(storage_dir, exist_ok=True)
    db_path = os.path.join(storage_dir, "agent_memory.db")
    
    # Initialize DB (Sync for schema creation safety)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Table for Document Versioning
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL,
                content TEXT,
                instruction TEXT,
                version INTEGER,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Initialization Error: {e}")

    return db_path

class AgentStorage(AsyncSqliteDb):
    """
    Extended Storage class to handle Document Versioning.
    """
    def __init__(self, db_file: str, **kwargs):
        self.db_file_path = db_file
        super().__init__(db_url=f"sqlite+aiosqlite:///{db_file}", **kwargs)

    async def save_doc_version(self, doc_type: str, content: str, instruction: str):
        """
        Saves a new version of a document.
        """
        try:
             # Use the explicitly stored path
             path = self.db_file_path
             
             with sqlite3.connect(path) as conn:
                 cursor = conn.cursor()
                 
                 # Get max version
                 cursor.execute("SELECT MAX(version) FROM doc_versions WHERE doc_type = ?", (doc_type,))
                 row = cursor.fetchone()
                 current_version = row[0] if row and row[0] is not None else 0
                 new_version = current_version + 1
                 
                 cursor.execute("""
                    INSERT INTO doc_versions (doc_type, content, instruction, version, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                 """, (doc_type, content, instruction, new_version, time.time()))
                 conn.commit()
        except Exception as e:
             print(f"Error saving doc version: {e}")

def get_agent_storage(project_root: str = None):
    """
    Restituisce l'oggetto Storage configurato su SQLite.
    I dati persistono nel file 'agent_memory.db' nella directory appropriata.
    """
    db_file = get_agent_db_path(project_root)
    
    # Init Schema
    try:
        with sqlite3.connect(db_file) as conn:
             cursor = conn.cursor()
             cursor.execute("""
                CREATE TABLE IF NOT EXISTS doc_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_type TEXT NOT NULL,
                    content TEXT,
                    instruction TEXT,
                    version INTEGER,
                    timestamp REAL
                )
             """)
             conn.commit()
    except: pass

    # Return our extended class
    return AgentStorage(
        db_file=db_file,
    )

async def list_sessions_with_summary(project_root: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Restituisce la lista delle sessioni con informazioni di riepilogo.
    Ogni sessione include:
    - session_id, created_at, updated_at
    - last_request: l'ultimo input dell'utente (se disponibile)
    - summary: il riepilogo della sessione (se disponibile)
    - team_id, agent_id, session_type
    """
    import json
    storage = get_agent_storage(project_root=project_root)

    try:
        # Ottieni le sessioni come dizionari grezzi (i campi JSON sono ancora stringhe)
        try:
             sessions = await storage.get_sessions(session_type=SessionType.AGENT,deserialize=True)
        except Exception as e:
             # Se la tabella non esiste (nuovo progetto), ritorna lista vuota
             logger.warning(f"Error reading sessions (might be new project): {e}")
             return []

        if not sessions:
            return []

        result = []
        for session in sessions:
            # session è un dict con i campi della tabella
            session_dict = session if isinstance(session, dict) else session.to_dict()

            # Estrai l'ultima richiesta dall'array runs
            last_request = None
            runs_raw = session_dict.get('runs')
            if runs_raw and isinstance(runs_raw, str):
                try:
                    runs = json.loads(runs_raw)
                    if isinstance(runs, list) and len(runs) > 0:
                        # Prendi l'ultima run (la più recente)
                        last_run = runs[-1]
                        # L'input potrebbe essere un dict con campo 'input_content'
                        input_data = last_run.get('input', {})
                        if isinstance(input_data, dict):
                            last_request = input_data.get('input_content')
                        elif isinstance(input_data, str):
                            last_request = input_data
                except json.JSONDecodeError:
                    pass
            elif isinstance(runs_raw, list) and len(runs_raw) > 0:
                # Se runs è già una lista (deserializzata)
                last_run = runs_raw[-1]
                input_data = last_run.get('input', {})
                if isinstance(input_data, dict):
                    last_request = input_data.get('input_content')
                elif isinstance(input_data, str):
                    last_request = input_data

            # Prepara l'oggetto risultato
            session_info = {
                'session_id': session_dict.get('session_id'),
                'session_type': session_dict.get('session_type'),
                'team_id': session_dict.get('team_id'),
                'agent_id': session_dict.get('agent_id'),
                'created_at': session_dict.get('created_at'),
                'created_at_formatted': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session_dict.get('created_at'))) if session_dict.get('created_at') else None,
                'updated_at': session_dict.get('updated_at'),
                'updated_at_formatted': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session_dict.get('updated_at'))) if session_dict.get('updated_at') else None,
                'last_request': last_request,
                'summary': session_dict.get('summary'),
                'user_id': session_dict.get('user_id'),
            }
            result.append(session_info)

        # Ordina per updated_at discendente (più recenti prima)
        result.sort(key=lambda x: x.get('updated_at') or 0, reverse=True)
        return result

    except Exception as e:
        print(f"Errore durante il recupero sessioni con riepilogo: {e}")
        return []

async def get_session_info(session_id: str, project_root: str = None) -> Optional[Dict[str, Any]]:
    """
    Restituisce informazioni dettagliate su una specifica sessione.
    """
    storage = get_agent_storage(project_root=project_root)

    try:
        session = await storage.get_session(
            session_id=session_id,
            deserialize=False
        )

        if not session:
            return None

        session_dict = session if isinstance(session, dict) else session.to_dict()

        # Formatta timestamp
        if session_dict.get('created_at'):
            session_dict['created_at_formatted'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(session_dict['created_at']))
        if session_dict.get('updated_at'):
            session_dict['updated_at_formatted'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(session_dict['updated_at']))

        return session_dict

    except Exception as e:
        print(f"Errore durante il recupero sessione {session_id}: {e}")
        return None


async def delete_session(session_id: str, project_root: str = None) -> bool:
    """
    Cancella una sessione dal database.

    Args:
        session_id: ID della sessione da cancellare
        project_root: Path del progetto (opzionale)

    Returns:
        True se la sessione è stata cancellata, False altrimenti
    """
    storage = get_agent_storage(project_root=project_root)

    try:
        return await storage.delete_session(session_id)
    except Exception as e:
        print(f"Errore durante la cancellazione sessione {session_id}: {e}")
        return False


async def get_session_with_runs(session_id: str, project_root: str = None) -> Optional[Dict[str, Any]]:
    """
    Restituisce una sessione con i runs deserializzati.

    Args:
        session_id: ID della sessione
        project_root: Path del progetto (opzionale)

    Returns:
        Dizionario della sessione con runs deserializzati, None se non trovata
    """
    storage = get_agent_storage(project_root=project_root)

    try:
        session = await storage.get_session(
            session_type=SessionType.AGENT,
            session_id=session_id,
            deserialize=True
        )

        if not session:
            return None

        session_dict = session if isinstance(session, dict) else session.to_dict()

        # Formatta timestamp
        if session_dict.get('created_at'):
            session_dict['created_at_formatted'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(session_dict['created_at']))
        if session_dict.get('updated_at'):
            session_dict['updated_at_formatted'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                time.localtime(session_dict['updated_at']))

        return session_dict

    except Exception as e:
        print(f"Errore durante il recupero sessione con runs {session_id}: {e}")
        return None