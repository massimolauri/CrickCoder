import os
import logging
import asyncio
import time
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

from src.core.storage.storage import TABLE_NAME
from src.core.runtime.project_init import get_db_path
from src.core.indexing.indexer_engine import UniversalCodeIndexer
from src.core.runtime.watcher import start_watcher

logger = logging.getLogger(__name__)

@dataclass
class ActiveContext:
    indexer: UniversalCodeIndexer
    observer: Any
    ref_count: int = 1
    last_used: float = 0.0

class CodebaseRegistry:
    """
    Singleton that manages File Watchers.
    SUPPORTS multiple concurrent projects and sessions.
    """
    def __init__(self):
        self._active_contexts: Dict[str, ActiveContext] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = 1800  # 30 minuti in secondi
        self._last_cleanup = time.time()

    async def _cleanup_inactive(self):
        """
        Rimuove progetti inattivi da più di cleanup_interval.
        Ferma progetti che non sono stati usati da più di 30 minuti,
        indipendentemente da ref_count (gestisce tab chiuse senza release).
        """
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        async with self._lock:
            to_remove = []
            for path, ctx in self._active_contexts.items():
                inactive_time = current_time - ctx.last_used
                if inactive_time > self._cleanup_interval:
                    to_remove.append(path)
                    logger.debug(f"Progetto inattivo da {inactive_time:.0f}s: {os.path.basename(path)} (ref_count: {ctx.ref_count})")

            for path in to_remove:
                await self._stop_context(path)
                del self._active_contexts[path]
                logger.info(f"Cleanup: rimosso progetto inattivo {os.path.basename(path)}")

            self._last_cleanup = current_time

    async def _stop_context(self, path: str):
        """Ferma watcher e indexer per un progetto specifico."""
        ctx = self._active_contexts.get(path)
        if not ctx:
            return

        if ctx.observer:
            try:
                # Esegui operazioni bloccanti in thread separato per non bloccare il loop eventi
                loop = asyncio.get_running_loop()

                # Ferma l'observer
                await loop.run_in_executor(None, ctx.observer.stop)

                # Aspettiamo il thread con timeout per evitare zombie
                def join_observer():
                    ctx.observer.join(timeout=5)
                    return ctx.observer.is_alive()

                is_alive = await loop.run_in_executor(None, join_observer)
                if is_alive:
                    logger.warning(f"Watcher thread ancora attivo dopo timeout per {path}")
            except Exception as e:
                logger.error(f"Errore fermando watcher per {path}: {e}")

        logger.info(f"Stopped watcher per: {os.path.basename(path)}")

    async def _create_context(self, abs_path: str) -> ActiveContext:
        """Crea un nuovo contesto per un progetto."""
        logger.info(f"Starting Services for: {abs_path}")

        # Init Indexer
        db_path = get_db_path(abs_path)
        indexer = UniversalCodeIndexer(db_path, TABLE_NAME)

        # Sync in thread separato per non bloccare il loop eventi
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, indexer.sync_project, abs_path)

        # Start Watcher
        observer = start_watcher(indexer, abs_path)

        return ActiveContext(indexer=indexer, observer=observer, ref_count=1, last_used=time.time())

    def _normalize_path(self, raw_path: str) -> str:
        return os.path.abspath(raw_path.strip('"').strip("'"))

    async def get_existing_indexer(self, raw_path: str) -> Optional[UniversalCodeIndexer]:
        """Returns the indexer if already loaded in RAM (thread-safe)."""
        abs_path = self._normalize_path(raw_path)
        async with self._lock:
            ctx = self._active_contexts.get(abs_path)
            if ctx:
                ctx.last_used = time.time()
                return ctx.indexer
            return None

    async def ensure_initialized(self, raw_path: str) -> None:
        """
        Attiva un progetto. Se già attivo, incrementa il reference count.
        Supporta più progetti contemporaneamente.
        """
        # Esegui cleanup periodico prima di acquisire lock
        await self._cleanup_inactive()

        abs_path = self._normalize_path(raw_path)

        if not os.path.exists(abs_path):
            raise ValueError(f"Path not found: {abs_path}")

        async with self._lock:

            # 1. Cache Hit: Progetto già attivo
            if abs_path in self._active_contexts:
                ctx = self._active_contexts[abs_path]
                ctx.ref_count += 1
                ctx.last_used = time.time()
                logger.debug(f"Incrementato ref_count per {abs_path}: {ctx.ref_count}")
                return

            # 2. Crea nuovo contesto
            ctx = await self._create_context(abs_path)
            self._active_contexts[abs_path] = ctx
            logger.info(f"Nuovo progetto attivato: {abs_path} (ref_count: {ctx.ref_count})")

    async def shutdown(self):
        """Ferma tutti i watcher (chiamato alla chiusura del server)."""
        async with self._lock:
            for path, ctx in list(self._active_contexts.items()):
                await self._stop_context(path)
                logger.info(f"Stopped watcher per: {os.path.basename(path)}")

            self._active_contexts.clear()
            logger.info("Tutti i progetti fermati")

    async def release(self, raw_path: str):
        """
        Rilascia un progetto (decrementa ref_count).
        Se ref_count raggiunge 0, il progetto sarà fermato dopo il timeout di cleanup.
        """
        abs_path = self._normalize_path(raw_path)

        async with self._lock:
            if abs_path not in self._active_contexts:
                logger.warning(f"Tentativo di rilasciare progetto non attivo: {abs_path}")
                return

            ctx = self._active_contexts[abs_path]
            ctx.ref_count -= 1
            ctx.last_used = time.time()

            logger.debug(f"Decrementato ref_count per {abs_path}: {ctx.ref_count}")

            if ctx.ref_count == 0:
                logger.info(f"Progetto {abs_path} ora inattivo (sara' rimosso dal cleanup)")

    async def get_active_projects(self):
        """Restituisce lista dei progetti attivi con ref_count."""
        async with self._lock:
            return {
                path: {
                    "ref_count": ctx.ref_count,
                    "last_used": ctx.last_used,
                    "has_observer": ctx.observer is not None
                }
                for path, ctx in self._active_contexts.items()
            }

# Global Instance
codebase_registry = CodebaseRegistry()