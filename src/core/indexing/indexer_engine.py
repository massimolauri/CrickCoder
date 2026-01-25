import os
import hashlib
import json
import pathspec
import time
import threading
from typing import Dict, List, Optional

# --- Agno Imports ---
from agno.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb, SearchType
from src.core.storage.embedder import get_shared_embedder

# --- Chunking Imports ---
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

# Configurazione Crick (opzionale)
from src.core.indexing.ignore import load_crickignore_rules

class UniversalCodeIndexer:
    def __init__(self, db_path: str, table_name: str):
        self.db_path = db_path
        self.table_name = table_name
        self._lock = threading.RLock()  # Lock per sincronizzare accessi al database
        
        # -----------------------------------------------------------
        # 1. CONFIGURAZIONE ADATTIVA
        # -----------------------------------------------------------
        # File sotto i 15k caratteri (circa 3k token) restano INTERI.
        # Jina v2 regge fino a 8k token, quindi siamo sicuri.
        self.SMALL_FILE_THRESHOLD = 30000 

        # -----------------------------------------------------------
        # 2. EMBEDDER: Jina v2 (Shared Singleton)
        # -----------------------------------------------------------
        self.embedder = get_shared_embedder()
        
        # -----------------------------------------------------------
        # 3. VECTOR DB
        # -----------------------------------------------------------
        self.vector_db = LanceDb(
            table_name=self.table_name,
            uri=self.db_path,
            embedder=self.embedder,
            search_type=SearchType.hybrid, 
            reranker=False
        )
        
        
        # Inizializza Knowledge Base di Agno
        self.knowledge = Knowledge(
            name="agnostic_codebase",
            vector_db=self.vector_db
        )

        # -----------------------------------------------------------
        # 4. CHUNKING TOOLS (Per file > 15k caratteri)
        # -----------------------------------------------------------
        self.LANG_MAP = {
            ".py": Language.PYTHON,
            ".js": Language.JS,
            ".jsx": Language.JS,
            ".ts": Language.TS, 
            ".tsx": Language.TS,
            ".java": Language.JAVA,
            ".go": Language.GO,
            ".rs": Language.RUST,
            ".cpp": Language.CPP, 
            ".c": Language.CPP,
            ".php": Language.PHP,
            ".html": Language.HTML,
            ".css": Language.HTML
        }

        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ">", " ", ""]
        )

    def _get_splitter(self, filename: str):
        """Helper per scegliere lo splitter corretto."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.LANG_MAP:
            return RecursiveCharacterTextSplitter.from_language(
                language=self.LANG_MAP[ext],
                chunk_size=30000,
                chunk_overlap=2000
            )
        return self.fallback_splitter

    # ==========================================
    # 1. CORE LOGIC (ADAPTIVE UPSERT)
    # ==========================================
    
    def upsert_file(self, full_path: str, root_dir: str, verbose=True):
        # 1. Skip binari
        if self._is_binary_file(full_path): return

        with self._lock:
            try:
                # 2. Calcolo Path Relativo Standardizzato
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                if rel_path.startswith("./"): rel_path = rel_path[2:]
            
                # 3. Lettura Sicura (Text Mode + UTF-8 + Ignore Errors)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    return # File illeggibile o lockato
            
                if not content.strip(): return 

                # 4. Calcolo Hash SHA256 (Coerente con Watcher)
                current_hash = self._compute_content_hash(content)
                file_len = len(content)

                # 5. Logica Chunking Adattiva
                docs = []
                if file_len < self.SMALL_FILE_THRESHOLD:
                    # File piccolo -> 1 Chunk unico
                    docs = [Document(page_content=content)]
                    if verbose: print(f"⚡ [UPSERT] {rel_path} (Intero: {file_len} chars)")
                else:
                    # File grande -> Split Intelligente
                    splitter = self._get_splitter(rel_path)
                    try: 
                        docs = splitter.create_documents([content])
                    except Exception: 
                        docs = self.fallback_splitter.create_documents([content])
                    if verbose: print(f"⚡ [UPSERT] {rel_path} (Chunked: {len(docs)} parts)")

                # 6. Pulizia Preventiva (Cruciale per evitare chunk orfani)
                # Se prima il file aveva 5 chunk e ora ne ha 3, dobbiamo rimuovere i vecchi 5.
                self.delete_file(full_path, root_dir, verbose=False)

                # 7. Preparazione Payload per Agno
                contents_to_add = []
                for idx, doc in enumerate(docs):
                    chunk_text = doc.page_content
                    
                    # Formattazione XML-style per aiutare l'LLM a capire dove inizia/finisce il file
                    rag_content = self._format_repomix_style(rel_path, chunk_text)
                    
                    # ID Univoco Stabile (basato su path e indice)
                    chunk_id = f"{rel_path}#{idx}"

                    contents_to_add.append({
                        "name": chunk_id,          # Agno userà questo per generare il suo ID interno
                        "text_content": rag_content,
                        "metadata": {
                            "path": rel_path,
                            "hash": current_hash,
                            "chunk_index": idx,
                            "total_chunks": len(docs),
                            "is_whole_file": len(docs) == 1,
                            "last_modified": time.time() 
                        },
                        "upsert": True,            # Sovrascrive se l'ID esiste
                        "skip_if_exists": False    # Forza l'aggiornamento (perché sappiamo che è cambiato)
                    })

                # 8. Scrittura Batch nel DB
                if contents_to_add:
                    self.knowledge.add_contents(contents_to_add)

            except Exception as e:
              print(f"❌ [ERROR] {rel_path if 'rel_path' in locals() else full_path}: {e}")

    def delete_file(self, full_path: str, root_dir: str, verbose=True):
        """Cancella tutti i chunk associati a un file usando i metadati."""
        rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
        if rel_path.startswith("./"): rel_path = rel_path[2:]

        try:
            # Rimuove vettori dove metadata.path == rel_path
            # Usiamo self.knowledge.remove_vectors_by_metadata se disponibile,
            # altrimenti fallback sul vector_db diretto per sicurezza.
            
            # Opzione A: Via Agno (Se supportato e testato)
            # self.knowledge.remove_vectors_by_metadata({"path": rel_path})
            
            # Opzione B: Via VectorDB diretto (Più sicuro per LanceDB specifico)
            success = self.vector_db.delete_by_metadata({"path": rel_path})
            
            if verbose and success: 
                print(f"🗑️  [DELETE] {rel_path}")
        except Exception as e:
            if "Table not initialized" in str(e): return
            print(f"❌ [DELETE ERROR] {e}")

    # ==========================================
    # 2. INDICI & SYNC
    # ==========================================

    def create_hybrid_indexes(self):
        """Ricostruisce gli indici accedendo alla proprietà .table di LanceDb."""
        try:
            # Controllo esistenza tramite wrapper
            if not self.vector_db.exists() or self.vector_db.table is None:
                return
            
            # Accesso diretto alla tabella sottostante mantenuta dalla classe LanceDb
            tbl = self.vector_db.table
            row_count = tbl.count_rows()
            print(f"⚙️  Analisi DB: trovate {row_count} righe.")

            # Indice Testuale (FTS)
            # Nota: La tua classe salva tutto in "payload", Agno mette il contenuto lì dentro.
            try: 
                tbl.create_fts_index("payload", use_tantivy=True, replace=True)
                self.vector_db.fts_index_exists = True
                print("✅ FTS Index aggiornato.")
            except Exception as e: 
                print(f"⚠️ FTS Skip: {e}")

            # Indice Vettoriale (IVF-PQ)
            if row_count > 2000:
                import math
                partitions = 2 ** int(math.log2(row_count / 20))
                partitions = max(2, min(256, partitions))
                
                # _vector_col è una proprietà della tua classe LanceDb
                vector_col = self.vector_db._vector_col
                
                tbl.create_index(
                    metric="cosine", 
                    vector_column_name=vector_col,
                    num_partitions=partitions, 
                    num_sub_vectors=96, 
                    replace=True
                )
                print("✅ Vector Index ottimizzato.")
            
        except Exception as e:
            print(f"⚠️  Manutenzione indici fallita: {e}")

    def sync_project(self, root_dir: str):
        """Scansiona la cartella e aggiorna il DB (CON DEBUG)."""
        print(f"[SYNC] Avvio analisi su: {root_dir}")
        
        # 1. Recupero stati
        disk_files = self._scan_disk_hashes(root_dir)
        db_state = self._get_db_state() 

        # DEBUG: Stato generale
        print(f"📊 [DEBUG STATS] Files su Disco: {len(disk_files)} | Files nel DB: {len(db_state)}")

        to_upsert = []
        to_delete = []

        # 2. Rileva modifiche (Nuovi file o Hash cambiati)
        print("🔍 [DEBUG CHECK] Analisi differenze...")
        for path, disk_hash in disk_files.items():
            # CASO A: Il file non è nel DB (Nuovo)
            if path not in db_state:
                print(f"   ➕ [NEW] {path}")
                to_upsert.append(path)
            
            # CASO B: C'è ma l'hash è diverso (Modificato)
            elif db_state[path] != disk_hash:
                db_hash = db_state[path]
                # Stampa i primi 8 caratteri degli hash per confronto
                print(f"   ✏️ [MOD] {path}")
                print(f"       └─ DISK: {disk_hash[:8]}...  vs  DB: {db_hash[:8]}...")
                to_upsert.append(path)
        
        # 3. Rileva cancellazioni
        for path in db_state:
            if path not in disk_files:
                print(f"   🗑️ [DEL] {path}")
                to_delete.append(path)

        # 4. Esecuzione
        if not to_upsert and not to_delete:
            print("[SYNC] ✅ Nessun cambiamento. DB aggiornato.")
            return

        print(f"[SYNC] Rilevati: +{len(to_upsert)} Upsert, -{len(to_delete)} Delete.")
        
        # Esecuzione Cancellazioni
        for p in to_delete:
            self.delete_file(os.path.join(root_dir, p), root_dir, verbose=False)
            
        # Esecuzione Inserimenti
        for i, p in enumerate(to_upsert, 1):
            print(f"   ⏳ Processing [{i}/{len(to_upsert)}]: {p}", end="\r")
            self.upsert_file(os.path.join(root_dir, p), root_dir, verbose=False)
            
        print("\n[SYNC] Completato.")
        self.create_hybrid_indexes()

    # ==========================================
    # 3. HELPER PRIVATI
    # ==========================================
    
    def _scan_disk_hashes(self, root_dir) -> Dict[str, str]:
        """
        Scansiona il disco. CORRETTO per ignorare estensioni .crickignore.
        """
        files_map = {}
        
        # 1. Carichiamo sia directory CHE estensioni
        try: 
            ignore_dirs, ignore_exts, _ = load_crickignore_rules(root_dir)
        except: 
            ignore_dirs, ignore_exts = [], []
        
        # Carica .gitignore per regole extra
        ignore_spec = None
        git_path = os.path.join(root_dir, ".gitignore")
        if os.path.exists(git_path):
             try:
                 with open(git_path, "r", encoding="utf-8") as f: 
                     ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
             except: pass

        for root, dirs, files in os.walk(root_dir):
            # Filtra le directory ignorate (es. node_modules)
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            
            for file in files:
                if file.startswith("."): continue
                
                # --- FIX ESTENSIONI ---
                # Controlla se il file finisce con una delle estensioni vietate
                if any(file.endswith(ext) for ext in ignore_exts):
                    continue
                # ----------------------

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                if rel_path.startswith("./"): rel_path = rel_path[2:]

                if ignore_spec and ignore_spec.match_file(rel_path): continue
                if self._is_binary_file(full_path): continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        files_map[rel_path] = self._compute_content_hash(content)
                except: pass
                
        return files_map

    def _get_db_state(self) -> Dict[str, str]:
    
        state: Dict[str, str] = {}
        
        try:
            # Usa il wrapper per controllare l'esistenza
            if not self.vector_db.exists() or self.vector_db.table is None:
                return {}

            # Accesso alla tabella sottostante tramite proprietà della classe LanceDb
            tbl = self.vector_db.table
            
            if tbl.count_rows() == 0: return {}

            # Scarica solo payload
            try:
                df = tbl.search().select(["payload"]).limit(None).to_pandas()
            except Exception:
                return {}

            if df.empty: return {}

            # Parsing del payload JSON
            for _, row in df.iterrows():
                try:
                    payload_raw = row["payload"]
                    # Deserializza se è stringa
                    payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
                    
                    if not payload: continue
                    
                    # La classe LanceDb salva i metadati dentro 'meta_data'
                    meta = payload.get("meta_data", {})
                    
                    path = meta.get("path")
                    file_hash = meta.get("hash")
                    chunk_idx = meta.get("chunk_index", 0)

                    # Solo chunk 0 per evitare duplicati
                    if path and file_hash and str(chunk_idx) == "0":
                        state[path] = file_hash
                except Exception:
                    continue

            return state

        except Exception as e:
            print(f"❌ [DB READ ERROR] {e}")
            return {}

    def _is_binary_file(self, filepath):
        try:
            with open(filepath, 'rb') as f: return b'\0' in f.read(1024)
        except: return True

    def _format_repomix_style(self, path, content):
        ext = os.path.splitext(path)[1]
        return f"""<file path="{path}" extension="{ext}">\n{content}\n</file>"""
    
    def get_stored_hash(self, rel_path: str) -> Optional[str]:
        """
        Recupera l'hash salvato per un file specifico senza aprire nuove connessioni.
        Usa la funzione search con filtri della classe LanceDb.
        """
        try:
            # Usiamo il metodo search della tua classe LanceDb.
            # Passiamo query vuota e filtriamo per path nei metadati.
            results = self.vector_db.search(
                query="", 
                limit=1, 
                filters={"path": rel_path}
            )
            
            if results and len(results) > 0:
                # LanceDb restituisce oggetti Document, accediamo a meta_data
                return results[0].meta_data.get("hash")
            
            return None
        except Exception as e:
            print(f"⚠️ Errore recupero hash per {rel_path}: {e}")
            return None

    def search(self, query: str, limit: int = 5):
        """
        Esegue una ricerca semantica/ibrida sulla codebase.
        """
        return self.vector_db.search(query=query, limit=limit)

    def reset(self):
        """
        Cancella completamente la tabella e la ricrea vuota.
        Utile per ripartire da zero.
        """
        print(f"⚠️ RESET: Cancellazione tabella {self.table_name}...")
        self.vector_db.drop()
        self.vector_db.create()
        print("✅ Database resettato.")
    def _compute_content_hash(self, content: str) -> str:
        """
        Calcola SHA256 normalizzando i line-endings.
        Garantisce coerenza tra Windows (File System) e DB.
        """
        if content is None: return ""
        
        # 1. Normalizza CR/LF in LF (Cruciale per Windows)
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        
        # 2. Usa SHA256 (Standard Agno/LanceDB)
        return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()  