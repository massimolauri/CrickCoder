import logging
import os
from typing import AsyncGenerator, Optional, Any, List, Dict
import asyncio
import re
from agno.agent import Agent
from src.agents.factory import build_agents
from src.models import LLMSettings

# --- Setup Logging ---
logger = logging.getLogger(__name__)

class VibingManager:
    """
    Central Controller (Facade). 
    Directly routes requests to specific agents (CODER, ARCHITECT, etc.)
    without an intermediary Orchestrator or Team Leader.
    """

    def __init__(self, session_id: str, project_root: str, auto_approval: bool = True, llm_settings: Optional[LLMSettings] = None, selected_theme_id: Optional[str] = None, enable_parallel: bool = False):
        self.session_id = session_id
        self.project_root = project_root
        self.enable_parallel = enable_parallel
        self.llm_settings = llm_settings

        # 1. Build specialized Agents via Factory
        # The factory returns a map: {"CODER": coder_obj, "ARCHITECT": arch_obj}
        # auto_approval is now True by default as per your new architecture
        self.agents_map: Dict[str, Agent] = build_agents(project_root, session_id, auto_approval, llm_settings, selected_theme_id)

    async def arun(
        self, 
        message: str, 
        agent_id: str,  # Directly identified by the frontend
        stream: bool = True, 
        stream_events: bool = True,
        yield_run_output: bool = True,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """
        Routes the user message directly to the specified agent.
        """
        
        # 1. Select the specific agent from the map
        # agent_id corresponds to the key in the factory (e.g., "CODER")
        active_agent = self.agents_map.get(agent_id.upper())
        
        if not active_agent:
            error_msg = f"Agent '{agent_id}' not found in current project context."
            logger.error(f"{error_msg}")
            raise ValueError(error_msg)

        logger.info(f"Routing request to: {agent_id} | Session: {self.session_id}")

        # --- 0. Context Injection (Shadow Workspace) ---
        from src.core.runtime.shadow_workspace import ShadowWorkspace
        # We need a stable run_id for this turn to track changes.
        # If kwargs has run_id use it, else generate (though typically run_id is internal to Agent)
        # Ideally we want the SAME run_id that the agent receives.
        # Since Agno generates run_id internally if not passed, we might be out of sync if we generate one here.
        # HOWEVER, we can simple trigger the context with a "Turn ID".
        # Let's generate a unique ID for this 'Action Turn' which suffices for the Undo feature.
        import uuid
        current_run_context_id = str(uuid.uuid4())
        
        ShadowWorkspace.get_instance().set_context(
            project_root=self.project_root,
            session_id=self.session_id,
            run_id=current_run_context_id
        )

        # --- Context Injection: Read Task List from Brain ---
        # The agents are now instructed via their sys prompts to proactively read the 
        # task.md files natively using their tools (brain_tool.read_document).
        # We no longer forcefully append it to the chat history to prevent 
        # O(N) context limits being hit rapidly from duplicated history injections.
        try:
             brain_task_path = os.path.join(self.project_root, ".crick", "sessions", self.session_id, "brain", "task.md")
             if os.path.exists(brain_task_path):
                 pass # Agents read this on their own now
        except Exception as e:
            logger.warning(f"Failed to check task context: {e}")

        # 2. Check for Parallel Execution Route
        # Automatically trigger parallel execution if there are uncompleted [PARALLEL] tasks and the target is CODER,
        # OR if the user explicitly types the command.
        parallel_tasks_count = 0
        brain_task_path = os.path.join(self.project_root, ".crick", "sessions", self.session_id, "brain", "task.md")
        
        has_parallel_command = "/parallel" in message.lower() or "[parallel]" in message.lower()
        should_auto_parallel = False
        
        if os.path.exists(brain_task_path):
            with open(brain_task_path, "r", encoding="utf-8") as f:
                task_content = f.read()
            for line in task_content.splitlines():
                if "- [ ]" in line and "[PARALLEL]" in line:
                    parallel_tasks_count += 1
                    
        if agent_id.upper() == "CODER" and parallel_tasks_count > 0:
            should_auto_parallel = True

        if has_parallel_command or (self.enable_parallel and should_auto_parallel):
            logger.info(f"Parallel execution triggered (Count: {parallel_tasks_count}, Command: {has_parallel_command}, Auto: {should_auto_parallel})")

            async for parallel_event in self.execute_parallel_plan():
                 yield parallel_event
            return # Exit early, do not run the standard sequential agent

        # 3. Proxy Execution Stream
        # Yield metadata event locally first
        yield {
            "type": "meta",
            "shadow_run_id": current_run_context_id,
            "agent": agent_id
        }

        # Directly call the agent's arun method
        async for event in active_agent.arun(
            message,
            stream=stream,
            stream_events=stream_events,
            yield_run_output=yield_run_output,
            **kwargs
        ):
            # Ensure the agent_name is injected for UI consistency 
            if hasattr(event, "agent_name") and not event.agent_name:
                event.agent_name = active_agent.name
            
            # Inject shadow_run_id into RunResponse objects if possible, for correlation
            if hasattr(event, "shadow_run_id"):
                 pass # Already set?
            else:
                 # We can't easily monkeypatch internal Pydantic models of Agno on the fly without risk.
                 # Rely on the initial "meta" event for the UI to track the ID.
                 pass

            yield event

    async def execute_parallel_plan(self) -> AsyncGenerator[Any, None]:
        """
        Reads task.md, identifies [PARALLEL] tasks, and executes them concurrently 
        by spawning multiple ephemeral Coder instances using asyncio.gather.
        """
        brain_task_path = os.path.join(self.project_root, ".crick", "sessions", self.session_id, "brain", "task.md")
        if not os.path.exists(brain_task_path):
             yield {"type": "error", "message": "No task.md found to execute in parallel."}
             return

        with open(brain_task_path, "r", encoding="utf-8") as f:
             task_content = f.read()

        # Regex to find lines like: "- [ ] [PARALLEL] Do something"
        # We look for uncompleted tasks with the exact tag.
        parallel_tasks = []
        for line in task_content.splitlines():
             if "- [ ]" in line and "[PARALLEL]" in line:
                 # Extract task instruction
                 task_instruction = line.split("[PARALLEL]")[-1].strip()
                 parallel_tasks.append(task_instruction)

        if not parallel_tasks:
             yield {"type": "content", "content": "\n\n⚠️ No uncompleted `[PARALLEL]` tasks found in `task.md`.\n\n", "agent": "Orchestrator"}
             return

        # Notify frontend that parallel mode is starting
        yield {
            "type": "parallel_start",
            "tasks": [{"index": i, "description": t} for i, t in enumerate(parallel_tasks)],
            "count": len(parallel_tasks),
            "agent": "Orchestrator"
        }

        # Build ephemeral agents inline for each parallel task
        base_coder = self.agents_map.get("CODER")
        if not base_coder:
             yield {"type": "error", "message": "Base Coder agent not found in factory context. Cannot extract model."}
             return

        # We need an asyncio Queue to stream events from multiple workers back to this synchronous-looking generator
        event_queue = asyncio.Queue()

        async def worker_task(idx: int, task_desc: str):
             # Build the ephemeral agent locally
             
             import platform
             from agno.agent import Agent
             from src.prompts.loader import load_prompt
             from src.tools.crickcoder_file_tools import CrickCoderFileTools
             from src.tools.crickcoder_shell_tools import CrickCoderShellTools
             from src.tools.crick_brain_tools import CrickBrainTools
             from pathlib import Path

             current_os = platform.system()
             os_context = f"SYSTEM OS: {current_os}."

             # Tools
             brain_tools = CrickBrainTools(
                 project_root=self.project_root,
                 llm_settings=self.llm_settings,
                 session_id=self.session_id
             )
             file_tools = CrickCoderFileTools(
                 base_dir=Path(self.project_root),
                 enable_confirmation=False # Auto mode for subtasks
             )
             shell_tools = CrickCoderShellTools(
                 base_dir=Path(self.project_root),
                 timeout_seconds=120,
                 enable_confirmation=False,
                 session_id=f"{self.session_id}_ephemeral_{idx}"
             )

             agent_name = f"Coder P-{idx+1}"

             ephemeral_agent = Agent(
                 name=agent_name,
                 role="Parallel Worker",
                 model=base_coder.model, # Re-use the existing initialized model connection
                 tools=[brain_tools, file_tools, shell_tools],
                 instructions=[
                     load_prompt("ephemeral_coder.md", model_id=base_coder.model.id),
                     os_context
                 ],
                 debug_mode=True,
                 markdown=True
             )
             
             full_response = ""
             
             # Notify frontend this worker started
             await event_queue.put({
                 "type": "parallel_progress",
                 "task_index": idx,
                 "task_description": task_desc,
                 "status": "started",
                 "agent": agent_name
             })
             
             try:
                 async for ev in ephemeral_agent.arun(
                     f"Execute this specific parallel subtask: {task_desc}",
                     stream=True,
                     stream_events=True
                 ):
                     # Inject agent name so the UI knows WHO is speaking
                     if hasattr(ev, 'agent') and not ev.agent:
                         ev.agent = agent_name
                     elif isinstance(ev, dict) and "agent" not in ev:
                         ev["agent"] = agent_name
                         
                     # Accumulate content for final summary
                     ev_type = getattr(ev, 'type', None) if not isinstance(ev, dict) else ev.get('type')
                     if ev_type == 'content':
                         content_val = getattr(ev, 'content', '') if not isinstance(ev, dict) else ev.get('content', '')
                         if content_val:
                             full_response += content_val
                     else:
                         # Forward ONLY non-content events (tool_start, tool_end, error, meta) to the frontend
                         # This prevents "text salading" in the UI when multiple agents speak at once.
                         await event_queue.put(ev)
                         
                 # Notify frontend this worker completed
                 await event_queue.put({
                     "type": "parallel_progress",
                     "task_index": idx,
                     "task_description": task_desc,
                     "status": "completed",
                     "agent": agent_name
                 })
                 return {"status": "success", "task": task_desc, "output": full_response}
             except Exception as e:
                 error_msg = f"Error in {agent_name}: {str(e)}"
                 await event_queue.put({
                     "type": "parallel_progress",
                     "task_index": idx,
                     "task_description": task_desc,
                     "status": "failed",
                     "agent": agent_name
                 })
                 await event_queue.put({"type": "error", "message": error_msg, "agent": agent_name})
                 return {"status": "error", "task": task_desc, "error": str(e)}

        # Execute Concurrently
        import time
        start_time = time.time()
        
        yield {
            "type": "tool_start",
            "tool": "Parallel_Workers",
            "args": f"Running {len(parallel_tasks)} tasks concurrently...",
            "agent": "Orchestrator"
        }
        
        # We start the workers in the background
        worker_tasks = [asyncio.create_task(worker_task(i, t)) for i, t in enumerate(parallel_tasks)]
        
        # We need a task that waits for all workers to finish
        async def wait_all():
            results = await asyncio.gather(*worker_tasks)
            await event_queue.put({"type": "_INTERNAL_DONE", "results": results})
            
        asyncio.create_task(wait_all())
        
        # Now we consume the queue and yield to the frontend until it's done
        final_results = []
        while True:
            ev = await event_queue.get()
            
            if isinstance(ev, dict) and ev.get("type") == "_INTERNAL_DONE":
                final_results = ev.get("results", [])
                break
                
            yield ev
            
        yield {
            "type": "tool_end",
            "tool": "Parallel_Workers",
            "result": "Completed",
            "agent": "Orchestrator"
        }
        
        # Report Back
        end_time = time.time()
        duration = end_time - start_time
        
        summary = f"Parallel execution completed in {duration:.2f} seconds.\n\n"
        for idx, res in enumerate(final_results):
             if res["status"] == "success":
                 summary += f"✅ **Task {idx+1}**: {res['task']}\n"
             else:
                 summary += f"❌ **Task {idx+1}**: {res['task']} (Failed: {res['error']})\n"
        
        yield {"type": "content", "content": summary, "agent": "Orchestrator"}
        
        # Notify frontend parallel mode ended
        yield {
            "type": "parallel_end",
            "duration": round(duration, 2),
            "total": len(parallel_tasks),
            "succeeded": sum(1 for r in final_results if r["status"] == "success"),
            "failed": sum(1 for r in final_results if r["status"] == "error"),
            "agent": "Orchestrator"
        }
