import os
import time
import threading
import hashlib
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Caricamento configurazione (se esiste, altrimenti default vuoto)
from src.core.indexing.ignore import load_crickignore_rules

logger = logging.getLogger(__name__)

def get_file_hash(file_path, retries=5, delay=0.2):
    """
    Calcola l'hash SHA256 RESILIENTE.
    DEVE essere identico a UniversalCodeIndexer._compute_content_hash
    """
    for i in range(retries):
        try:
            hasher = hashlib.sha256() # <--- SHA256 (Non più MD5)
            
            # USIAMO 'r' (TEXT MODE) + utf-8 per normalizzare i ritorni a capo
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Normalizzazione manuale per sicurezza assoluta
            normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")
            
            hasher.update(normalized_content.encode('utf-8'))
            return hasher.hexdigest()

        except (PermissionError, OSError):
            time.sleep(delay)
        except FileNotFoundError:
            return None
        except Exception:
            return None
            
    return None

class ProjectWatcher(FileSystemEventHandler):
    """
    Gestisce gli eventi del FileSystem e orchestra l'Indexer.
    """
    def __init__(self, indexer, root_dir):
        self.indexer = indexer
        self.root_dir = os.path.abspath(root_dir)
        self.last_event_time = {}
        
        # 🔒 LOCK CRITICO: LanceDB embedded non supporta scritture multi-thread.
        # Questo semaforo mette in fila le richieste di modifica.
        self.db_lock = threading.Lock()

        # 🔒 Lock per sincronizzare accessi al dizionario last_event_time
        self.event_time_lock = threading.Lock()

        self._reload_ignore_rules()

    def _reload_ignore_rules(self):
        """Carica le regole .gitignore e .crickignore"""
        self.ignore_dirs, self.ignore_exts, _ = load_crickignore_rules(self.root_dir)
        
        # Directory di sistema/sicurezza da ignorare SEMPRE
        security_ignores = {
            ".git", ".crick", ".idea", ".vscode", "__pycache__", 
            "node_modules", "venv", ".venv", "env", "dist", "build",
            ".pytest_cache", ".mypy_cache", "lancedb_data", "target",
            "bin", "obj", ".history" # C# e cartelle history locali
        }
        
        clean_dirs = set(security_ignores)
        for d in self.ignore_dirs:
            # Normalizza i path (rimuove slash finali e backslash)
            clean = d.strip().replace("\\", "/").strip("/")
            if clean: clean_dirs.add(clean)
            
        self.ignore_dirs = list(clean_dirs)
        logger.info(f"Watcher attivo su: {os.path.basename(self.root_dir)}")

    def _should_ignore(self, path):
        """Determina se un file deve essere processato o ignorato."""
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(self.root_dir):
            return True
            
        rel_path = os.path.relpath(abs_path, self.root_dir).replace("\\", "/")
        if rel_path.startswith("./"): rel_path = rel_path[2:]
        
        parts = rel_path.split("/")
        filename = parts[-1]

        # 1. Ignora file temporanei/lock (comuni in Windows/Linux)
        if (filename.endswith("~") or 
            filename.endswith(".tmp") or 
            filename.startswith(".#") or 
            filename.endswith(".lock")):
            return True

        # 2. Gestione dinamica ignore file
        if filename == ".crickignore":
             logger.info("Ricarico regole ignore...")
             self._reload_ignore_rules()
             return True 

        # 3. Controllo Directory Ignorate
        for part in parts[:-1]:
            if part.startswith(".") and part != ".": return True # Directory nascoste (.git, .vscode)
            if part in self.ignore_dirs: return True

        # 4. Controllo Estensioni
        if any(filename.endswith(ext) for ext in self.ignore_exts):
            return True

        # 5. File di sistema indesiderati
        if filename.startswith(".") or filename in ["thumbs.db", ".DS_Store"]:
            return True

        return False

    def on_any_event(self, event):
        """Entry point per ogni evento del filesystem."""
        if event.is_directory: return
        if self._should_ignore(event.src_path): return

        # --- DEBOUNCE (Anti-Rimbalzo) ---
        # Evita che un "Salva" scateni 3 eventi (Modify, Modify, AttrChange)
        with self.event_time_lock:
            current_time = time.time()
            last_time = self.last_event_time.get(event.src_path, 0)
            if (current_time - last_time) < 1.0: # 1 secondo di cool-down
                return
            self.last_event_time[event.src_path] = current_time

        if event.event_type == 'moved':
            threading.Thread(
                target=self._run_move,
                args=(event.src_path, event.dest_path),
                daemon=True
            ).start()
            return

        elif event.event_type == "deleted":
            threading.Thread(target=self._run_delete, args=(event.src_path,), daemon=True).start()
        elif event.event_type in ["created", "modified"]:
            threading.Thread(target=self._run_upsert, args=(event.src_path,), daemon=True).start()

    def _run_move(self, src_path, dest_path):
        """
        Logica atomica per Move: Delete Old + Upsert New.
        Gestisce internamente i casi in cui uno dei path sia ignorato.
        """
        # Controlliamo se i path sono da ignorare
        ignore_src = self._should_ignore(src_path)
        ignore_dest = self._should_ignore(dest_path)

        # Se entrambi sono ignorati, esci subito
        if ignore_src and ignore_dest: return

        with self.db_lock:
            try:
                logger.info(f"Rilevato spostamento: {os.path.basename(src_path)} -> {os.path.basename(dest_path)}")
                
                # 1. Cancella vecchio (se non era ignorato)
                if not ignore_src:
                    self.indexer.delete_file(src_path, self.root_dir, verbose=False)
                    logger.info(f"   ↳ Vecchio rimosso.")

                # 2. Inserisci nuovo (se non è ignorato)
                if not ignore_dest:
                    self.indexer.upsert_file(dest_path, self.root_dir, verbose=False)
                    logger.info(f"   ↳ Nuovo indicizzato.")
            except Exception as e:
                logger.error(f"❌ Errore Watcher Move: {e}", exc_info=True)
                
    def _run_upsert(self, path):
        """Esegue l'aggiornamento nel DB se il contenuto è cambiato."""
        try:
            # 1. Calcolo Hash su Disco (con retry per lock)
            current_hash = get_file_hash(path)
            if not current_hash: 
                return # File vuoto o inaccessibile

            # 2. Recupero Hash dal DB
            # Con l'Adaptive Chunking, anche se il file è diviso in 10 pezzi, 
            # ogni pezzo ha metadata['hash'] uguale all'hash del file intero.
            # Quindi basta recuperare un qualsiasi chunk per fare il confronto.
            rel_path = os.path.relpath(path, self.root_dir).replace("\\", "/")
            stored_hash = None
            
            # Try-except per evitare crash se il DB è occupato in lettura
            try:
                # Assumiamo che l'indexer abbia questo metodo helper
                if hasattr(self.indexer, 'get_stored_hash'):
                    stored_hash = self.indexer.get_stored_hash(rel_path)
            except Exception: 
                pass # Se fallisce la lettura, procediamo all'upsert per sicurezza

            # 3. Check Differenziale
            if current_hash == stored_hash:
                # print(f"💤 Skip (Invariato): {os.path.basename(path)}")
                return

            # 4. Scrittura Atomica (Thread-Safe)
            with self.db_lock:
                logger.info(f"Rilevata modifica: {os.path.basename(path)}")
                # Chiama l'upsert intelligente (che deciderà se fare chunking o no)
                self.indexer.upsert_file(path, self.root_dir, verbose=True)

        except Exception as e:
            logger.error(f"Errore Watcher Upsert: {e}", exc_info=True)

    def _run_delete(self, path):
        """Gestisce la cancellazione sicura."""
        with self.db_lock:
            try:
                logger.info(f"Rilevata cancellazione: {os.path.basename(path)}")
                self.indexer.delete_file(path, self.root_dir, verbose=True)
            except Exception as e:
                logger.error(f"Errore Watcher Delete: {e}", exc_info=True)

def start_watcher(indexer, root_dir):
    """Avvia il processo di monitoraggio."""
    if not os.path.exists(root_dir):
        logger.error(f"Errore: La directory {root_dir} non esiste.")
        return None

    logger.info(f"Avvio Watcher su: {root_dir}")
    logger.info("   (Premi Ctrl+C per fermare)")
    
    event_handler = ProjectWatcher(indexer, root_dir)
    observer = Observer()
    observer.schedule(event_handler, root_dir, recursive=True)
    observer.start()
    return observer