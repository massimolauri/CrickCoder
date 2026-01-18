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
from src.core.manager import VibingManager
from src.core.streamer import event_stream_generator
from src.core.monitor import codebase_registry
from src.core.storage import generate_session_id, list_sessions_with_summary, delete_session, get_session_with_runs
from src.core.template_indexer import TemplateIndexer
from src.core.server_utils import transform_runs_to_messages, normalize_path

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("CrickCoderAPI")

# --- SERVER ROOT ---
SERVER_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Server is ready
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

# Ensure public directory exists
os.makedirs(os.path.join(SERVER_ROOT, "public", "templates"), exist_ok=True)

# Mount Static Files for Templates
app.mount("/public", StaticFiles(directory=os.path.join(SERVER_ROOT, "public")), name="public")

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
            llm_settings=req.llm_settings
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

        # Save ZIP temporarily
        temp_dir = os.path.join(SERVER_ROOT, ".temp_upload")
        os.makedirs(temp_dir, exist_ok=True)
        temp_zip_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        async def progress_generator():
            # USE SERVER_ROOT for Global Storage
            # Pass parsed settings to Indexer for AI Analysis
            indexer = TemplateIndexer(SERVER_ROOT, llm_settings=parsed_settings)
            
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
        # USE SERVER_ROOT (Global)
        db_path = os.path.join(SERVER_ROOT, "knowledge_base", "templates_db")
        public_templates = os.path.join(SERVER_ROOT, "public", "templates")
        
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
        # 1. Delete Public Files
        public_dir = os.path.join(SERVER_ROOT, "public", "templates", template_id)
        if os.path.exists(public_dir):
            shutil.rmtree(public_dir)
            logger.info(f"Deleted public assets for {template_id}")

        # 2. Delete from DB
        db_path = os.path.join(SERVER_ROOT, "knowledge_base", "templates_db")
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
    # Reload=True allows hot-reloading during development
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)