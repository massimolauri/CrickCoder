import os
from typing import Optional
from agno.tools import Toolkit
from agno.agent import Agent
from src.core.storage.storage import get_agent_storage
from src.core.config.factory_models import build_model_for_runtime
from src.models import LLMSettings
from src.prompts.loader import load_prompt
from src.core.runtime.monitor import codebase_registry

class CrickBrainTools(Toolkit):
    def __init__(self, project_root: str, llm_settings: LLMSettings, session_id: str):
        super().__init__(name="crick_brain_tools")
        self.project_root = project_root
        self.llm_settings = llm_settings
        self.session_id = session_id
        
        # New Storage Path: .crick/sessions/<session_id>/brain/
        # This ensures isolation per session.
        self.brain_dir = os.path.join(self.project_root, ".crick", "sessions", self.session_id, "brain")
        os.makedirs(self.brain_dir, exist_ok=True)
        
        self.register(self.read_document)
        self.register(self.manage_task_list)
        self.register(self.manage_implementation_plan)
        self.register(self.manage_walkthrough)
        self.register(self.clear_tasks)
        self.register(self.search_knowledge_base)

    def _get_path(self, filename: str) -> str:
        return os.path.join(self.brain_dir, filename)

    async def _version_document(self, doc_type: str, content: str, instruction: str):
        """Saves a version of the document to the SQLite DB."""
        try:
            storage = get_agent_storage(self.project_root)
            await storage.save_doc_version(
                doc_type=doc_type,
                content=content,
                instruction=instruction
            )
        except Exception as e:
            print(f"Warning: Failed to version document {doc_type}: {e}")

    async def _run_ephemeral_agent(self, file_path: str, instruction: str, doc_type: str) -> str:
        """
        Spawns an isolated, ephemeral agent to update a documentation file.
        """
        current_content = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                current_content = f.read()
        else:
             # Create empty file if not exists to allow reading
             with open(file_path, "w", encoding="utf-8") as f:
                 f.write("")

        # Build a lightweight model for this specifc task
        model = build_model_for_runtime(
            provider=self.llm_settings.provider,
            model_id=self.llm_settings.model_id,
            temperature=0.1, # Low temp for precise formatting
            api_key=self.llm_settings.api_key,
            base_url=self.llm_settings.base_url
        )

        # Specialized System Prompt based on Doc Type
        if doc_type == "task.md":
            system_prompt = load_prompt("brain/task_manager.md")
        elif doc_type == "implementation_plan.md":
            system_prompt = load_prompt("brain/plan_manager.md")
        else: # walkthrough or generic
             system_prompt = load_prompt("brain/doc_manager.md")

        agent = Agent(
            model=model,
            instructions=system_prompt,
            markdown=True
            # No storage, no history -> Ephemeral & Isolated
        )

        user_msg = f"""
CURRENT CONTENT:
{current_content}

INSTRUCTION:
{instruction}

Update the file.
"""
        response = await agent.arun(user_msg)
        new_content = response.content

        # Save to File System
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Versioning
        await self._version_document(doc_type, new_content, instruction)

        return f"Successfully updated {os.path.basename(file_path)}."

    def read_document(self, filename: str) -> str:
        """
        Reads the content of a document (task.md, implementation_plan.md, etc.)
        Args:
            filename: The name of the file (e.g. 'task.md')
        """
        path = self._get_path(filename)
        if not os.path.exists(path):
            return f"File {filename} does not exist in brain."
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    async def manage_task_list(self, instruction: str) -> str:
        """
        Updates the task.md file. Use this to mark tasks as done, add new tasks, or update progress.
        Args:
            instruction: Natural language instruction (e.g., "Mark 'Setup DB' as done", "Add task 'Fix bug'").
        """
        return await self._run_ephemeral_agent(self._get_path("task.md"), instruction, "task.md")

    async def manage_implementation_plan(self, instruction: str) -> str:
        """
        Updates the implementation_plan.md file. Use this during the Planning phase.
        Args:
            instruction: Instruction on what to update (e.g., "Add a section for 'Auth'").
        """
        return await self._run_ephemeral_agent(self._get_path("implementation_plan.md"), instruction, "implementation_plan.md")

    async def manage_walkthrough(self, instruction: str) -> str:
        """
        Updates the walkthrough.md file. Use this during the Reporting phase.
        Args:
            instruction: Details of what was accomplished and verified.
        """
        return await self._run_ephemeral_agent(self._get_path("walkthrough.md"), instruction, "walkthrough.md")
        
    async def clear_tasks(self) -> str:
        """
        Completely wipes the task.md file. Use this ONLY when the user explicitly asks to 'forget tasks', 'clear tasks', or 'reset session'.
        """
        path = self._get_path("task.md")
        empty_content = "# Project Tasks\n\nNo active tasks."
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(empty_content)
            
        await self._version_document("task.md", empty_content, "User requested full task clear.")
        return "Task list has been completely reset."

    async def search_knowledge_base(self, query: str, limit: int = 5) -> str:
        """
        Searches the vector knowledge base for relevant code and documentation.

        Args:
            query: Natural language query describing what you're looking for.
            limit: Maximum number of results to return (default: 5).

        Returns:
            Formatted search results with file paths and relevant snippets.
        """
        try:
            print(f"[CrickBrainTools] search_knowledge_base: {query}, limit={limit}")
            # Get the indexer for this project
            indexer = await codebase_registry.get_existing_indexer(self.project_root)
            if not indexer:
                return f"Error: Knowledge base not initialized for project {self.project_root}. Please ensure the project is properly set up."

            # Execute search
            results = indexer.search(query, limit=limit)

            if not results:
                return f"No results found for query: '{query}'"

            # Format results
            output = f"## Knowledge Base Search Results for '{query}'\n\n"
            for i, doc in enumerate(results):
                # Extract metadata and content
                meta = getattr(doc, 'meta_data', {}) or getattr(doc, 'metadata', {})
                content = getattr(doc, 'content', '') or getattr(doc, 'page_content', '')
                path = meta.get('path', 'Unknown')
                chunk_idx = meta.get('chunk_index', 0)
                total_chunks = meta.get('total_chunks', 1)

                output += f"**{i+1}. {path}**"
                if total_chunks > 1:
                    output += f" (chunk {chunk_idx+1}/{total_chunks})"
                output += "\n"

                # Show a preview of the content (truncated)
                preview = content[:300] + "..." if len(content) > 300 else content
                output += f"```\n{preview}\n```\n\n"

            return output

        except Exception as e:
            return f"Error searching knowledge base: {str(e)}"
