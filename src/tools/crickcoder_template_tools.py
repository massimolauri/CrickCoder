import os
import shutil
import lancedb
from typing import Optional, List, Dict, Any
from agno.tools import Toolkit
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.agent import Agent
from src.core.storage.embedder import get_shared_embedder
from src.models import LLMSettings
from src.core.config.factory_models import build_model_for_runtime
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
        
        # GLOBAL USER PATH: ~/.crickcoder
        self.global_crick_dir = os.path.join(os.path.expanduser("~"), ".crickcoder")
        
        # Use Global Knowledge Base for Templates
        self.db_path = os.path.join(self.global_crick_dir, "knowledge_base", "templates_db")
        
        # --- BOOTSTRAP: Copy System Templates if Global DB missing ---
        if not os.path.exists(self.db_path):
            bundled_db_path = os.path.join(self.server_root, "knowledge_base", "templates_db")
            if os.path.exists(bundled_db_path):
                try:
                    # Copy the pre-filled LanceDB
                    shutil.copytree(bundled_db_path, self.db_path)
                    print(f"Bootstrapped System Templates to {self.db_path}")
                except Exception as e:
                    print(f"[WARN] Failed to copy system templates: {e}")
        
        # Shared Embedder (Cached Singleton)
        self.embedder = get_shared_embedder()

        self.register(self.search_templates)
        self.register(self.list_installed_templates)
        self.register(self.install_template)
        self.register(self.adapt_template_component)

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
        
        # 1. Resolve Source Path (Check Global User Dir, then Bundled Server Root)
        # Check ~/.crickcoder/public/templates/<id>/assets
        global_source = os.path.join(self.global_crick_dir, "public", "templates", template_id, "assets")
        # Check Bundled/Deployed <server_root>/public/templates/<id>/assets
        bundled_source = os.path.join(self.server_root, "public", "templates", template_id, "assets")

        if os.path.exists(global_source):
             source_base = global_source
        elif os.path.exists(bundled_source):
             source_base = bundled_source
        else:
             return f"Error: Template assets '{template_id}' not found (Checked Global: {global_source}, Bundled: {bundled_source})."

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

    def adapt_template_component(self, template_id: str, selector: str, instructions: str) -> str:
        """
        Adapts a specific component from a template using a dedicated 'clean context' agent.
        
        Args:
            template_id: The ID of the template (e.g. "tema607").
            selector: The generic name or CSS selector of the component (e.g. "navbar", ".sidebar").
            instructions: User's requirements (e.g. "Change links to React Router, use blue theme").
            
        Returns:
            The fully adapted code ready to be inserted.
        """
        try:
            # 1. Internal Search to get RAW Content (Hidden from Main Chat)
            # We bypass the summary restriction here because the Ephemeral Agent NEEDS the code.
            raw_content = self._fetch_raw_component(template_id, selector)
            
            if not raw_content:
                return f"Error: Could not find component matching '{selector}' in template '{template_id}'."

            # 2. Prepare Context for Ephemeral Agent
            # Minimal Context: Raw Component + Essential Project Files (e.g. index.css for styling tokens)
            
            project_styles = ""
            try:
                # Try to read index.css or similar global styles to give the agent context on tokens
                style_path = os.path.join(self.project_root, "src", "index.css") # Assumption
                if os.path.exists(style_path):
                     with open(style_path, "r", encoding="utf-8") as f:
                         project_styles = f.read()
            except:
                pass # Optional
            
            context_msg = (
                f"### TARGET COMPONENT (Raw HTML/JS from Reference):\n```html\n{raw_content}\n```\n\n"
                f"### PROJECT CURRENT STYLES (index.css):\n```css\n{project_styles[:2000]}\n```\n\n" # Truncate Styles
                f"### ADAPTATION INSTRUCTIONS:\n{instructions}\n"
            )

            # 3. Spawn Ephemeral Agent
            if not self.llm_settings:
                 return "Error: LLM Settings required for Smart Adaptation."

            model = build_model_for_runtime(
                 provider=self.llm_settings.provider,
                 model_id=self.llm_settings.model_id,
                 temperature=0.1,
                 api_key=self.llm_settings.api_key,
                 base_url=self.llm_settings.base_url
            )
            
            adapter_agent = Agent(
                model=model,
                description="Component Adapter",
                instructions=(
                    "You are an expert Frontend Integration Specialist.\n"
                    "Your task is to ADAPT the provided 'Target Component' to match the 'Project Styles' and 'Instructions'.\n"
                    "Output ONLY the adapted code block (JSX/TSX/HTML). Do not explain."
                ),
                markdown=True
            )
            
            response = adapter_agent.run(context_msg)
            return f"## Adapted Component ({selector})\n\n{response.content}"

        except Exception as e:
            return f"Error adapting component: {str(e)}"

    def _fetch_raw_component(self, template_id: str, selector: str) -> Optional[str]:
        """Internal helper to fetch raw code by semantic search or exact selector match (simplified)."""
        try:
            vector_db = LanceDb(
                    table_name=template_id,
                    uri=self.db_path,
                    embedder=self.embedder,
                    search_type=SearchType.hybrid,
                    reranker=False
                )
            
            # Hybrid search for selector
            results = vector_db.search(selector, limit=1)
            if results:
                item = results[0]
                content = getattr(item, 'content', '') or getattr(item, 'page_content', '')
                # Enrich? The content stored IS the description usually, but we store 'code_snippet' in metadata!
                # Wait, in indexer:
                # "text_content": comp.description
                # "metadata": { ... "code_snippet": raw_code ... }
                # So we must return the code_snippet from metadata!
                
                meta = getattr(item, 'meta_data', {}) or getattr(item, 'metadata', {})
                return meta.get("code_snippet") or content
            return None
        except:
             return None

    def search_templates(self, query: str, template_id: Optional[str] = None, limit: int = 5) -> str:
        """
        Searches for visual components in templates. Returns SUMMARIES ONLY.
        
        Args:
            query: Description of what you need (e.g. "modern pricing table").
            template_id: Optional. Filter by template.
            limit: Functionally limited to 5 to prevent context overload.
            
        Returns:
            A list of "Candidate Components" with descriptions and IDs.
            DOES NOT return full code. Use 'adapt_template_component' to get the code.
        """
        if not os.path.exists(self.db_path):
            return "No templates installed."

        try:
            db = lancedb.connect(self.db_path)
            response = db.list_tables()
            table_names = getattr(response, 'tables', [])
            
            if not table_names:
                return "No templates installed."

            if template_id:
                if template_id not in table_names:
                    return f"Template '{template_id}' not found."
                tables_to_search = [template_id]
            else:
                tables_to_search = table_names
            
            # Cap limit strictly
            safe_limit = min(limit, 5) 
            all_results = []
            
            # Simple Search Loop
            for table_name in tables_to_search:
                vector_db = LanceDb(
                    table_name=table_name,
                    uri=self.db_path,
                    embedder=self.embedder,
                    search_type=SearchType.hybrid,
                    reranker=False
                )
                results = vector_db.search(query, limit=safe_limit)
                
                for res in results:
                     # Enrich
                     if hasattr(res, 'meta_data') and isinstance(res.meta_data, dict):
                          res.meta_data["source_template"] = table_name
                     all_results.append(res)

            # Format Output (Summaries Only)
            output = f"## Found Components for '{query}'\n\n"
            
            for i, item in enumerate(all_results[:safe_limit]):
                content = getattr(item, 'content', '') or getattr(item, 'page_content', '') # This is DESCRIPTION now
                meta = getattr(item, 'meta_data', {}) or getattr(item, 'metadata', {})
                
                name = meta.get("component_name", "Unknown")
                tmpl = meta.get("source_template", "?")
                category = meta.get("category", "UI")
                selector = meta.get("selector", "N/A")
                
                output += f"**{i+1}. {name}** ({category})\n"
                output += f"- **Source**: {tmpl}\n"
                output += f"- **Selector**: `{selector}`\n"
                output += f"- **Visual Description**: {content[:200]}...\n" # Truncate description
                output += f"> *To use: `adapt_template_component(template_id='{tmpl}', selector='{selector}', instructions='...')`*\n\n"

            return output

        except Exception as e:
            return f"Error searching templates: {str(e)}"

    def list_installed_templates(self) -> str:
        """
        Lists all the templates currently installed in the system.
        """
        if not os.path.exists(self.db_path):
            return f"No templates installed (Database not found at {self.db_path})."
            
        try:
            db = lancedb.connect(self.db_path)
            # list_tables() returns a response object with .tables attribute
            response = db.list_tables()
            
            # Access .tables if available, or try to iterate if not (fallback)
            tables = getattr(response, 'tables', [])
            
            if not tables:
                 return f"No templates installed (Database empty at {self.db_path})."
            
            return f"Installed Templates (from {self.db_path}): " + ", ".join(tables)
        except Exception as e:
            return f"Error listing templates from {self.db_path}: {str(e)}"
