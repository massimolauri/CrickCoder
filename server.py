import logging
import uvicorn
import datetime
import os
from uuid import uuid4
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
# --- Local Imports ---
from src.models import ChatRequest, ContinueRequest
from src.core.manager import VibingManager
from src.core.streamer import event_stream_generator
from src.core.monitor import codebase_registry
from src.core.storage import generate_session_id, list_sessions_with_summary, delete_session, get_session_with_runs

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("CrickCoderAPI")

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

# --- HELPER FUNCTIONS ---

def transform_runs_to_messages(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trasforma una lista di runs Agno in una lista di ChatMessage per la UI.

    Ogni run rappresenta una esecuzione di un agente in risposta a un input utente.
    Struttura attesa di una run:
    - input: dict con input_content (messaggio utente)
    - events: lista di eventi (RunContent, ToolCallStarted, ToolCallCompleted)
    - content: contenuto testuale aggregato (opzionale)
    - agent_name: nome dell'agente
    - created_at: timestamp

    Ritorna lista di ChatMessage nel formato:
    - id: numero (timestamp)
    - role: 'user' o 'assistant'
    - content: string (per messaggi utente)
    - timeline: lista di TimelineItem (per messaggi assistant)
    """
    messages = []
    message_id_counter = 1  # Simple counter for IDs

    for run in runs:
        # 1. Crea messaggio utente dall'input
        input_data = run.get('input', {})
        user_content = None

        if isinstance(input_data, dict):
            user_content = input_data.get('input_content') or input_data.get('message')
        elif isinstance(input_data, str):
            user_content = input_data

        if user_content:
            user_message = {
                'id': message_id_counter,
                'role': 'user',
                'content': user_content
            }
            messages.append(user_message)
            message_id_counter += 1

        # 2. Crea messaggio assistant dagli eventi
        events = run.get('events', [])
        agent_name = run.get('agent_name', 'System')

        if events or run.get('content'):
            assistant_message = {
                'id': message_id_counter,
                'role': 'assistant',
                'timeline': []
            }
            message_id_counter += 1

            timeline = assistant_message['timeline']
            pending_tools = {}  # Mappa tool_name -> index nella timeline

            # Processa eventi in ordine
            for event in events:
                event_type = event.get('event', '') if isinstance(event, dict) else getattr(event, 'event', '')

                # RunContent -> text timeline item
                if event_type in ['RunContent', 'IntermediateRunContent']:
                    content = event.get('content', '')
                    if content:
                        # Cerca se c'è già un item text dello stesso agente
                        if timeline and timeline[-1]['type'] == 'text' and timeline[-1]['agent'] == agent_name:
                            # Appendi al contenuto esistente
                            timeline[-1]['content'] += content
                        else:
                            # Nuovo item text
                            timeline.append({
                                'type': 'text',
                                'content': content,
                                'agent': agent_name
                            })

                # ToolCallStarted -> tool timeline item con status running
                elif event_type == 'ToolCallStarted':
                    tool_data = event.get('tool', {})
                    if isinstance(tool_data, dict):
                        tool_name = tool_data.get('tool_name', 'unknown')
                        tool_args = tool_data.get('tool_args', {})
                    else:
                        tool_name = getattr(tool_data, 'tool_name', 'unknown')
                        tool_args = getattr(tool_data, 'tool_args', {})

                    tool_item = {
                        'type': 'tool',
                        'tool': tool_name,
                        'args': tool_args,
                        'status': 'running',
                        'agent': agent_name
                    }
                    timeline.append(tool_item)
                    pending_tools[tool_name] = len(timeline) - 1

                # ToolCallCompleted -> aggiorna tool a completed o converte in terminal
                elif event_type == 'ToolCallCompleted':
                    tool_data = event.get('tool', {})
                    if isinstance(tool_data, dict):
                        tool_name = tool_data.get('tool_name', 'unknown')
                        result = str(tool_data.get('result', ''))
                    else:
                        tool_name = getattr(tool_data, 'tool_name', 'unknown')
                        result = str(getattr(tool_data, 'result', ''))

                    # Cerca l'ultimo tool con questo nome nello stato running
                    tool_index = pending_tools.get(tool_name)
                    if tool_index is not None and tool_index < len(timeline):
                        tool_item = timeline[tool_index]
                        if tool_item['type'] == 'tool' and tool_item['status'] == 'running':
                            # Verifica se è un tool terminale (shell/build)
                            is_terminal = ('Exit Code' in result or
                                          'shell' in tool_name.lower() or
                                          'build' in tool_name.lower())

                            if is_terminal:
                                # Converti in terminal item
                                timeline[tool_index] = {
                                    'type': 'terminal',
                                    'command': tool_name,
                                    'output': result,
                                    'agent': agent_name
                                }
                            else:
                                # Aggiorna a completed
                                tool_item['status'] = 'completed'
                                timeline[tool_index] = tool_item

                            # Rimuovi dai pending
                            del pending_tools[tool_name]

            # Se non ci sono eventi ma c'è content, crea un item text dal content
            if not timeline and run.get('content'):
                timeline.append({
                    'type': 'text',
                    'content': run['content'],
                    'agent': agent_name
                })

            # Aggiungi il messaggio assistant solo se ha timeline
            if timeline:
                messages.append(assistant_message)

    return messages

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
    return {"agents": ["ARCHITECT", "CODER"]}

def normalize_path(project_path: str) -> str:
    return os.path.abspath(project_path.strip('"').strip("'"))

if __name__ == "__main__":
    # Reload=True allows hot-reloading during development
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)