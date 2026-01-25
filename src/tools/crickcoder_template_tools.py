import os
import lancedb
from typing import Optional, List, Dict, Any
from agno.tools import Toolkit
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.agent import Agent
from src.core.embedder import get_shared_embedder
from src.models import LLMSettings
from src.core.factory_models import build_model_for_runtime
from src.prompts.loader import load_prompt

class CrickCoderTemplateTools(Toolkit):
    def __init__(self, project_root: Optional[str] = None, llm_settings: Optional[LLMSettings] = None):
        super().__init__(name="template_tools")
        # If project_root is not provided, try to find it or use cwd
        if not project_root:
            self.project_root = os.getcwd()
        else:
            self.project_root = project_root
            
        self.llm_settings = llm_settings
            
        # FIX: Templates are Global (in SERVER_ROOT), not in User Project Root.
        # This file is in <SERVER_ROOT>/src/tools/crickcoder_template_tools.py
        # Go up 3 levels to find SERVER_ROOT
        current_file = os.path.abspath(__file__)
        self.server_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        
        self.db_path = os.path.join(self.server_root, "knowledge_base", "templates_db")
        
        # Shared Embedder (Cached Singleton)
        self.embedder = get_shared_embedder()

        self.register(self.search_templates)
        self.register(self.list_installed_templates)
        self.register(self.install_template)

    def install_template(self, template_id: str, target_path: str = ".") -> str:
        """
        Installs the selected template's assets into the current project.
        
        Args:
            template_id: The ID of the template (e.g., "tema607").
            target_path: Subdirectory to install into (e.g. "src/theme").
            
        Returns:
            Success or error message.
        """
        import shutil
        
        # 1. Resolve Source Path
        # Source Base: <SERVER_ROOT>/public/templates/<id>/assets
        source_base = os.path.join(self.server_root, "public", "templates", template_id, "assets")
        
        # Check if template/assets exist
        if not os.path.exists(source_base):
             return f"Error: Template assets '{template_id}' not found (checked: {source_base})."

        full_source = source_base

        # 2. Resolve Target Path (SECURE)
        # Ensure target_path cannot escape self.project_root
        
        # Sanitize target path (remove leading slashes/drive letters)
        safe_target_rel = target_path.strip("/\\").lstrip(".").lstrip("/\\") 
        if not safe_target_rel:
            safe_target_rel = "."
            
        full_target = os.path.join(self.project_root, safe_target_rel)
        
        # Double check containment
        if not os.path.normpath(full_target).startswith(os.path.normpath(self.project_root)):
             return f"Error: Invalid target path '{target_path}'. Must be within project root."

        # 3. Validation & Execution
        if not os.path.exists(full_source):
            return f"Error: Asset source '{full_source}' does not exist."

        try:
            # Source is DIR (assets folder)
            # We want to merge contents into Project Root + Target Path
            # shutil.copytree with dirs_exist_ok=True does exactly this (merges)
            os.makedirs(full_target, exist_ok=True)
            shutil.copytree(full_source, full_target, dirs_exist_ok=True)
            
            return f"SUCCESS: Template '{template_id}' installed into '{full_target}'."

        except Exception as e:
            return f"Error installing template: {str(e)}"

    def search_templates(self, query: str, template_id: Optional[str] = None, limit: int = 5, verbose: bool = False) -> str:
        """
        Searches for code snippets or logic within the installed templates.
        
        Args:
            query: The natural language search query (e.g., "login page component", "sidebar styling").
            template_id: Optional. If provided, searches only within that specific template.
            limit: Number of results to return.
            verbose: If True, returns full code snippets. If False (default), returns compact summaries.
            
        Returns:
            A string containing relevant code snippets and their file paths.
        """
        if not os.path.exists(self.db_path):
            return "No templates installed (Database not found)."

        try:
            db = lancedb.connect(self.db_path)
            # list_tables() returns a response object with .tables attribute
            response = db.list_tables()
            table_names = getattr(response, 'tables', [])
            
            if not table_names:
                return "No templates installed."

            # Determine which tables to search
            # If template_id is used, we only search that one.
            # Otherwise we search all available in table_names.
            if template_id:
                if template_id not in table_names:
                    return f"Template '{template_id}' not found."
                tables_to_search = [template_id]
            else:
                tables_to_search = table_names
            
            all_results = []

            # Accumulate ALL results from all tables first
            keys_seen = set()
            
            for table_name in tables_to_search:
                # table_name should be a string now.
                
                vector_db = LanceDb(
                    table_name=table_name,
                    uri=self.db_path,
                    embedder=self.embedder,
                    search_type=SearchType.hybrid,
                    reranker=False
                )
                
                # Perform Search - Fetch 'limit' per table to ensure coverage
                results = vector_db.search(query, limit=limit)
                
                for res in results:
                    # Enrich with template name
                    if hasattr(res, 'meta_data') and isinstance(res.meta_data, dict):
                         res.meta_data["source_template"] = table_name
                    elif hasattr(res, 'metadata') and isinstance(res.metadata, dict):
                         res.metadata["source_template"] = table_name
                    
                    # Deduplicate based on content hash or path + template
                    # (Simple dedup to avoid exact duplicates if any)
                    content = getattr(res, 'content', '') or getattr(res, 'page_content', '')
                    if content not in keys_seen:
                        keys_seen.add(content)
                        all_results.append(res)
            
            # Results are returned in natural order (or shuffled by the DB logic if any).
            # Explicit sorting by score/distance deemed unnecessary/incorrect for this use case.


            # Determine candidates for output
            # If using AI Filter, we can be more generous with input context
            candidate_limit = limit * 2 if self.llm_settings else limit
            final_candidates = all_results[:candidate_limit]
            
            # Format Output
            output = f"## Search Results for '{query}'"
            if template_id:
                output += f" in template '{template_id}'"
            output += "\n\n"

            # ------------------------------------------------------------------
            # SMART RAG LOGIC (Ephemeral Agent) - Only if LLMSettings provided
            # ------------------------------------------------------------------
            if self.llm_settings:
                # 1. Format Raw Context for the Agent
                raw_context = ""
                for i, item in enumerate(final_candidates): 
                    content = getattr(item, 'content', '') or getattr(item, 'page_content', '')
                    meta = getattr(item, 'meta_data', {}) or getattr(item, 'metadata', {})
                    path = meta.get("path", "unknown")
                    name = meta.get("component_name", "Unknown")
                    tmpl = meta.get("source_template", "unknown")
                    
                    # We send everything to the agent, let it decide what's relevant
                    raw_context += f"--- RESULT {i+1}: {name} (Template: {tmpl}, File: {path}) ---\n{content}\n\n"

                if not raw_context.strip():
                     return "No relevant templates found to analyze."

                # 2. Spawn Ephemeral Agent
                try:
                    model = build_model_for_runtime(
                        provider=self.llm_settings.provider,
                        model_id=self.llm_settings.model_id,
                        temperature=0.1, 
                        api_key=self.llm_settings.api_key,
                        base_url=self.llm_settings.base_url
                    )
                    
                    agent = Agent(
                        model=model,
                        description="Template Architect Agent",
                        instructions=load_prompt("brain/template_architect.md"),
                        markdown=True
                    )
                    
                    user_msg = f"USER QUERY: {query}\n\nRAW RESULTS:\n{raw_context}"
                    
                    # Run generic synchronous run 
                    response = agent.run(user_msg)
                    return f"## Smart Search Results (AI Filtered)\n\n{response.content}"
                    
                except Exception as ai_e:
                    # Fallback to standard listing if AI fails
                    output += f"\n*(Smart RAG failed: {ai_e}. Showing raw results below)*\n\n"
                    # Fallback to original limit
                    final_candidates = all_results[:limit]
            # ------------------------------------------------------------------
            # FALLBACK / LEGACY OUTPUT (If no LLMSettings or AI failed)
            # ------------------------------------------------------------------
            
            for i, item in enumerate(final_candidates): 
                # Agno Document uses 'content' and 'meta_data'
                content = getattr(item, 'content', '') or getattr(item, 'page_content', '')
                meta = getattr(item, 'meta_data', {}) or getattr(item, 'metadata', {})
                
                path = meta.get("path", "unknown")
                tmpl = meta.get("source_template", "unknown")
                
                # Extended Metadata from AI Indexing
                name = meta.get("component_name", "Unknown Component")
                category = meta.get("category", "UI Element")
                selector = meta.get("selector", "")
                code_snippet = meta.get("code_snippet", "")
                
                output += f"### Result {i+1}: {name} ({category})\n"
                output += f"**Template**: {tmpl}\n"
                output += f"**File**: {path}\n"
                output += f"**Selector**: `{selector}`\n"
                
                # Compact vs Verbose logic
                short_desc = (content[:300] + '...') if len(content) > 300 else content
                
                if verbose:
                    output += f"**Description**: {content}\n\n"
                    if code_snippet:
                        output += "**Code Snippet**:\n```html\n" + code_snippet + "\n```\n"
                    else:
                        output += "**Content**:\n```\n" + content + "\n```\n"
                else:
                    output += f"**Snippet Preview**: {short_desc}\n"
                    if code_snippet or len(content) > 300:
                        output += "*(Full code hidden. Use `verbose=True` to view)*\n"
                
                output += "\n---\n\n"

            return output

        except Exception as e:
            return f"Error searching templates: {str(e)}"

    def list_installed_templates(self) -> str:
        """
        Lists all the templates currently installed in the system.
        """
        if not os.path.exists(self.db_path):
            return "No templates installed."
            
        try:
            db = lancedb.connect(self.db_path)
            # list_tables() returns a response object with .tables attribute
            response = db.list_tables()
            
            # Access .tables if available, or try to iterate if not (fallback)
            tables = getattr(response, 'tables', [])
            
            if not tables:
                 return "No templates installed."
            
            return "Installed Templates: " + ", ".join(tables)
        except Exception as e:
            return f"Error listing templates: {str(e)}"
