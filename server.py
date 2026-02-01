import logging
import uvicorn
import datetime
import os
import shutil
import asyncio
import json
import lancedb

from contextlib import asynccontextmanager
from uuid import uuid4
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- Local Imports ---
from src.models import ChatRequest, ContinueRequest, LLMSettings
from src.core.runtime.manager import VibingManager
from src.core.runtime.streamer import event_stream_generator
from src.core.runtime.monitor import codebase_registry
from pydantic import BaseModel
from src.core.storage.storage import generate_session_id, list_sessions_with_summary, delete_session, get_session_with_runs
from src.core.indexing.template_indexer import TemplateIndexer
from src.core.runtime.server_utils import transform_runs_to_messages, normalize_path
from src.core.runtime.shadow_workspace import ShadowWorkspace
import difflib

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("CrickCoderAPI")

# --- SERVER ROOT ---
SERVER_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- GLOBAL USER ROOT (.crickcoder) ---
GLOBAL_CRICK_DIR = os.path.join(os.path.expanduser("~"), ".crickcoder")

# --- Bootstrap Function ---
def bootstrap_environment():
    """Bootstraps the global user environment from bundled assets."""
    logger.info(f"Checking Global Environment at: {GLOBAL_CRICK_DIR}")
    
    # 1. Base Directories
    global_public = os.path.join(GLOBAL_CRICK_DIR, "public", "templates")
    global_kb = os.path.join(GLOBAL_CRICK_DIR, "knowledge_base", "templates_db")
    
    os.makedirs(global_public, exist_ok=True)
    os.makedirs(os.path.dirname(global_kb), exist_ok=True)

    # 2. Copy Bundled Templates (Asset Source)
    bundled_public = os.path.join(SERVER_ROOT, "public", "templates")
    if os.path.exists(bundled_public):
        # We copy if global is empty to seed it
        try:
            # We copy if listdir is empty? Or just merge/overwrite existing system ones?
            # Safer to merge (dirs_exist_ok=True) so we update system templates on app update.
            # But we don't want to overwrite USER changes? 
            # For now, let's just ensure they exist.
            if not os.listdir(global_public):
                shutil.copytree(bundled_public, global_public, dirs_exist_ok=True)
                logger.info("📦 Bootstrapped Bundled Templates to Global Dir")
        except Exception as e:
            logger.error(f"Failed to bootstrap templates: {e}")

    # 3. Copy Bundled Knowledge Base (DB)
    bundled_kb = os.path.join(SERVER_ROOT, "knowledge_base", "templates_db")
    if os.path.exists(bundled_kb):
        if not os.path.exists(global_kb):
            try:
                shutil.copytree(bundled_kb, global_kb)
                logger.info("📦 Bootstrapped Knowledge Base to Global Dir")
            except Exception as e:
                logger.error(f"Failed to bootstrap Knowledge Base: {e}")


# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Bootstrap & Ready
    bootstrap_environment()
    logger.info("🚀 Crick Coder API Ready.")
    yield
    # Shutdown: Clean up all active file watchers to free resources
    await codebase_registry.shutdown()

# --- FastAPI Setup ---
app = FastAPI(title="Crick Coder API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure global public directory exists
os.makedirs(os.path.join(GLOBAL_CRICK_DIR, "public"), exist_ok=True)

# Mount Static Files from GLOBAL PUBLIC to support user templates
app.mount("/public", StaticFiles(directory=os.path.join(GLOBAL_CRICK_DIR, "public")), name="public")

@app.get("/api/project/brain/{filename}")
async def get_brain_file(filename: str, project_path: Optional[str] = Query(None), session_id: Optional[str] = Query(None)):
    """
    Returns the content of a file from the .crick/sessions/<session_id>/brain directory.
    """
    try:
        if not project_path:
             return {"content": "", "error": "Missing project_path query parameter"}
        
        if not session_id:
             return {"content": "", "error": "Missing session_id query parameter"}

        # Normalizza e verifica il path del progetto
        project_root = normalize_path(project_path=project_path)
        
        # DEBUG LOGGING

        
        if not os.path.exists(project_root):
            logger.error(f"Project root not found: {project_root}")
            return {"content": "", "error": "Project path not found"}

        brain_dir = os.path.join(project_root, ".crick", "sessions", session_id, "brain")
        file_path = os.path.join(brain_dir, filename)
        

        
        if not os.path.exists(file_path):
            # Proviamo a vedere se è un file nuovo e magari ancora non esiste
            logger.warning(f"File not found on disk: {file_path}")
            return {"content": "", "error": "File not found"}
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            logger.info(f"Read {len(content)} bytes from {filename}")
        return {"content": content}

    except Exception as e:
        return {"content": "", "error": str(e)}

@app.delete("/api/project/brain/task.md")
async def clear_brain_task_file(
    project_path: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    """
    Clears the task.md file for the specified session.
    """
    try:
        if not project_path or not session_id:
             raise HTTPException(status_code=400, detail="Missing project_path or session_id")
        
        project_root = normalize_path(project_path=project_path)
        brain_dir = os.path.join(project_root, ".crick", "sessions", session_id, "brain")
        file_path = os.path.join(brain_dir, "task.md")
        
        # Overwrite with empty default
        empty_content = "# Project Tasks\n\nNo active tasks."
        if os.path.exists(brain_dir): # Ensure dir exists
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(empty_content)
        
        return {"status": "success", "message": "Task list cleared."}

    except Exception as e:
        logger.error(f"Clear Task Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- UNDO / FILE API ---

class UndoRequest(BaseModel):
    files: Optional[List[str]] = None

@app.post("/api/runs/{run_id}/undo")
async def undo_run_changes(
    run_id: str,
    session_id: str = Query(...),
    project_path: str = Query(...),
    body: UndoRequest = None # Optional body
):
    try:
        project_root = normalize_path(project_path=project_path)
        
        target_files = body.files if body else None

        # Esegui Rollback
        success = ShadowWorkspace.get_instance().rollback(
            project_root=project_root,
            session_id=session_id,
            run_id=run_id,
            target_files=target_files
        )
        
        if success:
            msg = "Selected changes reverted" if target_files else f"Run {run_id} changes reverted."
            return {"status": "success", "message": msg}
        else:
            return {"status": "ignored", "message": "No changes found to revert for this run."}

    except Exception as e:
        logger.error(f"Undo Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs/{run_id}/files")
async def get_run_files(
    run_id: str,
    session_id: str = Query(...),
    project_path: str = Query(...)
):
    try:
        project_root = normalize_path(project_path=project_path)
        
        files = ShadowWorkspace.get_instance().get_run_changes(
            project_root=project_root,
            session_id=session_id,
            run_id=run_id
        )
        
        return {"files": files}

    except Exception as e:
        logger.error(f"Get Run Files Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/content")
async def get_file_content(path: str = Query(...), project_path: str = Query(...)):
    """Reads a file from the project safely."""
    try:
        project_root = normalize_path(project_path=project_path)
        abs_path = os.path.abspath(os.path.join(project_root, path))
        
        # Security check: ensure path is within project root
        if not abs_path.startswith(os.path.abspath(project_root)):
             raise HTTPException(status_code=403, detail="Access denied: File outside project root")
             
        if not os.path.exists(abs_path):
             raise HTTPException(status_code=404, detail="File not found")
             
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            
        return {"content": content, "path": path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/diff")
async def get_file_diff(
    files: List[str], # List of relative paths
    run_id: str = Query(...),
    session_id: str = Query(...),
    project_path: str = Query(...)
):
    """
    Returns diffs for the specified files against their shadow backup for this run.
    """
    try:
        project_root = normalize_path(project_path=project_path)
        shadow_ws = ShadowWorkspace.get_instance()
        # Ensure context is set for internal helper usage if needed, though we pass params explicitly usually
        
        diffs = {}
        
        for rel_path in files:
            abs_path = os.path.join(project_root, rel_path)
            
            # 1. Get Current Content
            current_content = ""
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    current_content = f.read()
            
            # 2. Get Shadow Content
            # Manually construct shadow path since ShadowWorkspace doesn't expose a 'read' method publicly
            # but we can use private helper logic re-implemented or just add a helper method.
            # Let's peek into the implementation detail for speed, or better, stick to the pattern:
            # .crick/history/<session_id>/<run_id>/<rel_path>
            shadow_path = os.path.join(project_root, ".crick", "history", session_id, run_id, rel_path)
            
            shadow_content = ""
            if os.path.exists(shadow_path):
                with open(shadow_path, "r", encoding="utf-8", errors="replace") as f:
                    shadow_content = f.read()
            else:
                # If shadow doesn't exist, maybe it was a new file?
                # If new file, shadow is empty (effectively).
                pass

            # 3. Generate Diff
            if current_content == shadow_content:
                continue

            diff_gen = difflib.unified_diff(
                shadow_content.splitlines(keepends=True),
                current_content.splitlines(keepends=True),
                fromfile=f"Original/{rel_path}",
                tofile=f"Modified/{rel_path}"
            )
            diff_text = "".join(diff_gen)
            
            diffs[rel_path] = diff_text
            
        return {"diffs": diffs}

    except Exception as e:
        logger.error(f"Diff Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS ---

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Starts a new conversation turn with a specific agent.
    1. Validates and initializes codebase context.
    2. Routes the request directly to the selected agent_id.
    3. Streams the execution events back to the client.
    """
    try:
        # Check if the project path is valid and initialize codebase monitoring
        await codebase_registry.ensure_initialized(req.project_path)

        # Retrieve or generate session ID to maintain conversation state
        session_id = req.session_id or generate_session_id()
        
        # Verify that an agent_id is provided, otherwise we don't know who to talk to
        if not req.agent_id:
            raise HTTPException(status_code=400, detail="agent_id is required for direct communication.")

        logger.info(f"🚀 Direct Agent Chat | Session: {session_id} | Target Agent: {req.agent_id}")

        # Instantiate Manager (Stateless Logic Facade)
        manager = VibingManager(
            session_id=session_id,
            project_root=req.project_path,
            auto_approval=req.auto_approval,
            llm_settings=req.llm_settings,
            selected_theme_id=req.selected_theme_id
        )

        # Delegate the streaming execution to the event generator
        # The manager will now use arun() on the specific agent instance
        return StreamingResponse(
            event_stream_generator(
                manager,
                method="run",
                prompt=req.message,
                session_id=session_id,
                agent_id=req.agent_id,
                project_path=req.project_path
            ),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Chat Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/templates/upload")
async def upload_template_zip(
    file: UploadFile = File(...),
    project_path: Optional[str] = Query(None), # Query param, optional and ignored
    llm_settings: str = Form(...) # JSON string of LLMSettings
):
    """
    Uploads a ZIP file containing a graphic template.
    1. Extracts ZIP
    2. Identifies Manifest (Template ID)
    3. Extracts Preview Image (theme_screen.png) to GLOBAL public folder
    4. Indexes content into GLOBAL LanceDB using provided LLM Settings
    """
    try:
        # Parse LLM Settings
        try:
            settings_dict = json.loads(llm_settings)
            parsed_settings = LLMSettings(**settings_dict)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid LLM Settings: {e}")

        # Save ZIP temporarily (Use Global Temp)
        temp_dir = os.path.join(GLOBAL_CRICK_DIR, ".temp_upload")
        os.makedirs(temp_dir, exist_ok=True)
        temp_zip_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        async def progress_generator():
            # USE GLOBAL DIRECTORY for Template Indexing
            # Pass parsed settings to Indexer for AI Analysis
            # Note: TemplateIndexer ignores project_root for global assets now, 
            # but passing GLOBAL_CRICK_DIR is cleaner context.
            indexer = TemplateIndexer(GLOBAL_CRICK_DIR, llm_settings=parsed_settings)
            
            try:
                for event in indexer.process_template_zip(temp_zip_path):
                    # SSE Format: data: <json>\n\n
                    yield f"data: {json.dumps(event)}\n\n"
                    
            except Exception as e:
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
            finally:
                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)

        return StreamingResponse(progress_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Upload Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/templates")
def list_templates(project_path: str = None):
    """
    Lists all installed templates by checking GLOBAL LanceDB tables and available preview images.
    Arg 'project_path' is ignored as templates are global.
    """
    try:
        # USE GLOBAL_CRICK_DIR (User Data)
        db_path = os.path.join(GLOBAL_CRICK_DIR, "knowledge_base", "templates_db")
        public_templates = os.path.join(GLOBAL_CRICK_DIR, "public", "templates")
        
        templates = []
        
        # 1. Get List from DB (if exists)
        if os.path.exists(db_path):
            try:
                db = lancedb.connect(db_path)
                table_names = db.table_names()
                
                for name in table_names:
                    # Check for preview image
                    public_dir = os.path.join(public_templates, name)
                    preview_path = os.path.join(public_dir, "theme_screen.png")
                    manifest_path = os.path.join(public_dir, "manifest.json")
                    
                    has_preview = os.path.exists(preview_path)
                    
                    # Default Metadata
                    metadata = {
                        "name": name.replace("-", " ").title(),
                        "description": "",
                        "author": "",
                        "version": ""
                    }

                    # Read Manifest if exists
                    if os.path.exists(manifest_path):
                        try:
                            with open(manifest_path, "r", encoding="utf-8") as f:
                                manifest_data = json.load(f)
                                metadata.update(manifest_data) # Override defaults
                        except Exception as e:
                            logger.warning(f"Error reading manifest for {name}: {e}")
                    
                    templates.append({
                        "id": name,
                        "name": metadata.get("name"),
                        "description": metadata.get("description"),
                        "author": metadata.get("author"),
                        "version": metadata.get("version"),
                        "preview_url": f"/public/templates/{name}/theme_screen.png" if has_preview else None,
                        "installed_at": None
                    })
            except Exception as e:
                logger.error(f"Error reading LanceDB: {e}")

        return {"templates": templates}
    except Exception as e:
         logger.error(f"List Templates Error: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    """
    Deletes a template:
    1. Removes the public/templates/<id> directory.
    2. Drops the table from LanceDB.
    """
    try:
        # 1. Delete Public Files (Global)
        public_dir = os.path.join(GLOBAL_CRICK_DIR, "public", "templates", template_id)
        if os.path.exists(public_dir):
            shutil.rmtree(public_dir)
            logger.info(f"Deleted public assets for {template_id}")

        # 2. Delete from DB (Global)
        db_path = os.path.join(GLOBAL_CRICK_DIR, "knowledge_base", "templates_db")
        if os.path.exists(db_path):
            try:
                db = lancedb.connect(db_path)
                db.drop_table(template_id)
                logger.info(f"Dropped table {template_id}")
            except Exception as e:
                # If table doesn't exist, we can ignore (maybe it was partial install)
                logger.warning(f"Could not drop table {template_id}: {e}")

        return {"status": "success", "message": f"Template {template_id} deleted."}

    except Exception as e:
        logger.error(f"Delete Template Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def get_sessions_endpoint(project_path: str):
    try:
        abs_path = normalize_path(project_path=project_path)
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=400, detail=f"Path not found: {abs_path}")

        sessions = await list_sessions_with_summary(project_root=abs_path)
        return {"project_path": abs_path, "sessions": sessions, "count": len(sessions)}
    except Exception as e:
        logger.error(f"List Sessions Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str, project_path: Optional[str] = None):
    try:
        root = normalize_path(project_path=project_path) if project_path else None
        success = await delete_session(session_id, project_root=root)

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"success": True, "session_id": session_id}
    except Exception as e:
        logger.error(f"Delete Session Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/history")
async def get_session_history_endpoint(session_id: str, project_path: Optional[str] = None):
    """
    Recupera la cronologia completa di una sessione.
    Trasforma i runs salvati nel formato ChatMessage per la UI.
    """
    try:
        # Normalizza il path se fornito
        root = normalize_path(project_path=project_path) if project_path else None

        # Ottieni la sessione con runs deserializzati
        session = await get_session_with_runs(session_id, project_root=root)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Estrai i runs
        runs = session.get('runs', [])
        if not runs:
            return {"messages": []}

        # Trasforma runs in messaggi
        messages = transform_runs_to_messages(runs)

        return {"messages": messages}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session History Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.get("/api/agents")
def get_agents():
    """Returns the list of available agents."""
    return {"agents": ["ARCHITECT", "PLANNER", "CODER"]}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable hot reloading")
    args = parser.parse_args()

    # Disable reload in production/standalone mode if not explicitly requested
    # But for dev keep it.
    import sys
    
    # Check if running in frozen mode (PyInstaller)
    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        # In frozen mode, passing the string "server:app" fails because uvicorn 
        # tries to import "server" which doesn't exist as a file.
        # We must pass the app object directly. Reload is not supported in frozen mode.
        # We also disable workers logic if any, just run simple.
        uvicorn.run(app, host=args.host, port=args.port, reload=False)
    else:
        # In dev mode, use string to enable hot reload
        uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)