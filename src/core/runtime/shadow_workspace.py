import os
import shutil
import json
import logging
import threading
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class ShadowWorkspace:
    _instance = None
    _lock = threading.RLock()

    def __init__(self):
        self.current_session_id: Optional[str] = None
        self.current_run_id: Optional[str] = None
        self.project_root: Optional[str] = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ShadowWorkspace()
        return cls._instance

    def set_context(self, project_root: str, session_id: str, run_id: str):
        """
        Sets the current execution context.
        Called by VibingManager before running an agent.
        """
        with self._lock:
            self.project_root = project_root
            self.current_session_id = session_id
            self.current_run_id = run_id

    def clear_context(self):
        with self._lock:
            self.current_session_id = None
            self.current_run_id = None
            self.project_root = None

    def _get_shadow_dir(self, session_id: str, run_id: str) -> str:
        if not self.project_root:
            raise ValueError("Project Root not set in ShadowWorkspace")
        return os.path.join(self.project_root, ".crick", "history", session_id, run_id)

    def snapshot(self, file_path: str):
        """
        Creates a backup of the file IF it hasn't been backed up for this run yet.
        """
        with self._lock:
            if not self.current_session_id or not self.current_run_id or not self.project_root:
                # If context is missing (e.g. unit tests or manual tool use), skip backup
                return

            try:
                abs_file_path = os.path.abspath(file_path)
                
                # Check if file exists (if it's a new file, nothing to backup)
                if not os.path.exists(abs_file_path):
                    return

                shadow_dir = self._get_shadow_dir(self.current_session_id, self.current_run_id)
                os.makedirs(shadow_dir, exist_ok=True)

                # Calculate relative path to preserve structure in shadow dir
                # e.g. src/utils/foo.py -> .crick/history/.../src/utils/foo.py
                try:
                    rel_path = os.path.relpath(abs_file_path, self.project_root)
                except ValueError:
                    # Windows drive letter mismatch or similar
                    logger.warning(f"Cannot backup file outside project root: {abs_file_path}")
                    return

                backup_path = os.path.join(shadow_dir, rel_path)

                # CRITICAL: Only backup ONCE per run (the original state before ANY edits in this run)
                if os.path.exists(backup_path):
                    return

                # Create parent dirs in shadow
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                
                shutil.copy2(abs_file_path, backup_path)
                logger.debug(f"[SNAP] Snapshot created: {rel_path}")
                
                # Update Manifest
                self._update_manifest(shadow_dir, rel_path)

            except Exception as e:
                logger.error(f"Failed to create snapshot for {file_path}: {e}")

    def _update_manifest(self, shadow_dir: str, rel_path: str):
        manifest_path = os.path.join(shadow_dir, "manifest.json")
        data = {"files": []}
        
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    data = json.load(f)
            except: pass
        
        if rel_path not in data["files"]:
            data["files"].append(rel_path)
            
        with open(manifest_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_run_changes(self, project_root: str, session_id: str, run_id: str) -> List[str]:
        """Returns list of relative file paths modified in a specific run."""
        try:
            self.project_root = project_root # Ensure root is known for this query
            shadow_dir = self._get_shadow_dir(session_id, run_id)
            manifest_path = os.path.join(shadow_dir, "manifest.json")
            
            if not os.path.exists(manifest_path):
                return []
                
            with open(manifest_path, "r") as f:
                data = json.load(f)
                return data.get("files", [])
        except Exception:
            return []

    def rollback(self, project_root: str, session_id: str, run_id: str, target_files: Optional[List[str]] = None) -> bool:
        """
        Restores files from the snapshot.
        If target_files is provided, only restores those specific files.
        Otherwise, restores ALL files modified in the run.
        """
        try:
            self.project_root = project_root
            shadow_dir = self._get_shadow_dir(session_id, run_id)
            
            # Get all modified files in this run
            run_files = self.get_run_changes(project_root, session_id, run_id)
            
            if not run_files:
                return False
                
            # Filter if specific files requested
            files_to_restore = run_files
            if target_files:
                # Validate that requested files are actually in the run info
                files_to_restore = [f for f in target_files if f in run_files]
                
            if not files_to_restore:
                return False

            logger.info(f"[ROLLBACK] Rolling back run {run_id} ({len(files_to_restore)} files)")
            
            for rel_path in files_to_restore:
                backup_path = os.path.join(shadow_dir, rel_path)
                original_path = os.path.join(project_root, rel_path)
                
                if os.path.exists(backup_path):
                    # Ensure parent dir exists
                    os.makedirs(os.path.dirname(original_path), exist_ok=True)
                    shutil.copy2(backup_path, original_path)
                    logger.info(f"Restored {rel_path}")
                else:
                    pass
            
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
