import json
import logging
import asyncio
from typing import Any, AsyncGenerator, cast

from agno.run import RunStatus

logger = logging.getLogger(__name__)

async def event_stream_generator(
    executable_object: Any,
    prompt: str = None,
    method: str = "run",
    run_id: str = None,
    message: str = None,
    project_path: str = None,
    **kwargs
) -> AsyncGenerator[str, None]:
    """
    Universal stream generator for Agno.
    Handles both 'run' and 'continue' statelessly.
    """
    current_run_id = run_id
    last_agent_name = getattr(executable_object, "name", "System")
    session_id = getattr(executable_object, "session_id", None)

    try:
        try:
            iterator = None

            # --- 1. START EXECUTION ---
            if method == "run":
                # Standard Run (Agent)
                iterator = executable_object.arun(
                    prompt,
                    stream=True,
                    stream_events=True,
                    yield_run_output=True,
                    **kwargs
                )

            elif method == "continue":
                # Resume Execution using Team's logic
                iterator = executable_object.acontinue_run(
                    run_id=run_id,
                    message=message,
                    stream=True,
                    stream_events=True,
                    yield_run_output=True
                )
            else:
                raise ValueError(f"Unknown method: {method}")

            # --- 2. CONSUME STREAM ---
            async for event in iterator:

                # --- A. CHECK FOR PAUSED STATUS (From Final Object) ---
                # We check if this event is the final output object and if it's paused.
                if hasattr(event, "status") and event.status == RunStatus.paused:
                    logger.info(f"⏸️ PAUSED STATE RECEIVED: {event.run_id}")

                    current_run_id = event.run_id

                    # Identify paused tool
                    paused_tool = "unknown"
                    if hasattr(event, "tools") and event.tools:
                        for tool in event.tools:
                            if getattr(tool, "is_paused", False):
                                paused_tool = tool.tool_name
                                break

                    # Send Payload to Frontend so it can call /continue later
                    payload = {
                        "type": "paused",
                        "run_id": current_run_id,
                        "session_id": session_id,
                        "agent_name": last_agent_name,
                        "tool": paused_tool
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    continue # Don't process this object as a standard event

                # --- B. STANDARD EVENT PROCESSING ---

                # Update IDs
                if hasattr(event, "run_id") and event.run_id:
                    current_run_id = event.run_id
                if hasattr(event, "agent_name") and event.agent_name:
                    last_agent_name = event.agent_name

                payload = {}
                event_type = getattr(event, "event", "")
                display_name = getattr(event, "agent_name", None) or getattr(event, "team_name", last_agent_name)

                # 1. Content
                if event_type in ["RunContent"] and event.content:
                    payload = {
                        "type": "content",
                        "content": event.content,
                        "agent": display_name
                    }

                # 2. Tool Start
                elif event_type in ["ToolCallStarted"]:
                    tool = getattr(event, "tool", None)
                    if tool:
                        payload = {
                            "type": "tool_start",
                            "agent": display_name,
                            "tool": tool.tool_name,
                            "args": tool.tool_args
                        }

                # 3. Tool End
                elif event_type in ["ToolCallCompleted"]:
                    tool = getattr(event, "tool", None)
                    if tool:
                        raw_res = str(tool.result)
                        preview = raw_res[:200] + "..." if len(raw_res) > 200 else raw_res
                        payload = {
                            "type": "tool_end",
                            "agent": display_name,
                            "tool": tool.tool_name,
                            "result": preview
                        }

                # 4. Intermediate Pause Event (fallback)
                elif getattr(event, "is_paused", False):
                     tool_name = getattr(event, "tool_call", {}).get("tool_name", "unknown")
                     payload = {
                        "type": "paused",
                        "run_id": current_run_id,
                        "session_id": session_id,
                        "agent_name": last_agent_name,
                        "tool": tool_name
                     }
                     yield f"data: {json.dumps(payload)}\n\n"
                     return

                # Send payload
                if payload:
                    yield f"data: {json.dumps(payload)}\n\n"

            yield "data: [DONE]\n\n"

        except asyncio.CancelledError:
            logger.warning("⚠️ Stream cancelled by client.")
            if current_run_id and hasattr(executable_object, "cancel_run"):
                try:
                    executable_object.cancel_run(current_run_id)
                except Exception as e:
                    logger.error(f"Error cancelling run: {e}")
            raise

        except Exception as e:
            logger.error(f"Critical stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    finally:
        if project_path:
            try:
                from src.core.monitor import codebase_registry
                await codebase_registry.release(project_path)
                logger.debug(f"Released project context for {project_path}")
            except Exception as e:
                logger.error(f"Error releasing project context: {e}")