import os
import lancedb
from typing import Optional, List, Dict, Any
from agno.tools import Toolkit
from agno.vectordb.lancedb import LanceDb, SearchType
from src.core.embedder import get_shared_embedder

class CrickCoderTemplateTools(Toolkit):
    def __init__(self, project_root: Optional[str] = None):
        super().__init__(name="template_tools")
        # If project_root is not provided, try to find it or use cwd
        if not project_root:
            self.project_root = os.getcwd()
        else:
            self.project_root = project_root
            
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
        self.register(self.install_template_assets)

    def install_template_assets(self, template_id: str, asset_path: str, target_path: str) -> str:
        """
        Copies static assets (folders or files) from the Template Archive to the current project.
        Use this to install CSS, JS, Images, or Fonts from a theme.

        Args:
            template_id: The ID of the template (e.g., "tema607").
            asset_path: The relative path inside the template assets (e.g., "css", "js/main.js", "." for root).
            target_path: The destination path in your project (e.g., "public/css", "src/assets").

        Returns:
            Success or error message.
        """
        import shutil

        # Source: <SERVER_ROOT>/public/templates/<id>/assets/<asset_path>
        source_base = os.path.join(self.server_root, "public", "templates", template_id, "assets")
        
        # Handle root access
        if asset_path == "." or asset_path == "/" or not asset_path:
             full_source = source_base
        else:
             full_source = os.path.join(source_base, asset_path)

        # Target: Relative to CWD (Project Root)
        full_target = os.path.abspath(target_path)

        # Smart Path Resolution
        if not os.path.exists(full_source):
            # Check if it's nested in a subfolder (common in ZIPs like 'theme/assets/css')
            root_contents = os.listdir(source_base)
            found_smart = False
            for item in root_contents:
                potential_path = os.path.join(source_base, item, asset_path)
                if os.path.isdir(os.path.join(source_base, item)) and os.path.exists(potential_path):
                    full_source = potential_path
                    found_smart = True
                    break
            
            if not found_smart:
                # Generate a helpful directory listing for the agent
                try:
                    available = []
                    for root, dirs, _ in os.walk(source_base):
                        for d in dirs:
                            rel = os.path.relpath(os.path.join(root, d), source_base)
                            if len(available) < 10: available.append(rel)
                    listing = ", ".join(available)
                except:
                    listing = "Error listing files"
                    
                return f"Error: Asset '{asset_path}' not found in {template_id}. Available dirs: [{listing}...]"

        try:
            # Determine effective target directory
            # If copying a DIRECTORY, full_target IS the new dir.
            # If copying a FILE, full_target might be the new file OR the dir to put it in.
            
            # Logic: If source is FILE, and target looks like a DIR (no extension) or user provided a dir path, 
            # we should append the filename.
            effective_target = full_target
            
            if not os.path.isdir(full_source): # Source is FILE
                # Heuristic: If target has no extension and doesn't exist, assume it's a DIR
                _, ext = os.path.splitext(full_target)
                if not ext and not os.path.exists(full_target):
                    # Make it a directory
                    os.makedirs(full_target, exist_ok=True)
                    # Append source filename
                    effective_target = os.path.join(full_target, os.path.basename(full_source))
                elif os.path.isdir(full_target):
                    # Target is existing directory
                    effective_target = os.path.join(full_target, os.path.basename(full_source))
                else:
                    # Target is a file path (e.g. public/css/custom.css)
                    # Ensure parent exists
                    os.makedirs(os.path.dirname(full_target), exist_ok=True)

            else: # Source is DIR
                 # Ensure parent of the new dir exists
                 os.makedirs(os.path.dirname(full_target), exist_ok=True)

            message = ""
            if os.path.isdir(full_source):
                # Copy Directory
                shutil.copytree(full_source, full_target, dirs_exist_ok=True)
                message = f"Directory '{asset_path}' installed to '{target_path}' (from {full_source})."
            else:
                # Copy File
                shutil.copy2(full_source, effective_target)
                message = f"File '{asset_path}' installed to '{effective_target}'."
            
            return f"SUCCESS: {message}"

        except Exception as e:
            return f"Error installing assets: {str(e)}"

    def search_templates(self, query: str, template_id: Optional[str] = None, limit: int = 5) -> str:
        """
        Searches for code snippets or logic within the installed templates.
        
        Args:
            query: The natural language search query (e.g., "login page component", "sidebar styling").
            template_id: Optional. If provided, searches only within that specific template.
            limit: Number of results to return.
            
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

            for table_name in tables_to_search:
                # table_name should be a string now.
                
                vector_db = LanceDb(
                    table_name=table_name,
                    uri=self.db_path,
                    embedder=self.embedder,
                    search_type=SearchType.hybrid,
                    reranker=False
                )
                
                # Perform Search
                results = vector_db.search(query, limit=limit)
                
                for res in results:
                    # Enrich with template name
                    # Agno Document uses 'content' and 'meta_data'
                    # We need to access the correct dict to inject source_template
                    if hasattr(res, 'meta_data') and isinstance(res.meta_data, dict):
                         res.meta_data["source_template"] = table_name
                    elif hasattr(res, 'metadata') and isinstance(res.metadata, dict):
                         res.metadata["source_template"] = table_name
                    
                    all_results.append(res)
            
            # Format Output
            output = f"## Search Results for '{query}'"
            if template_id:
                output += f" in template '{template_id}'"
            output += "\n\n"

            for i, item in enumerate(all_results[:limit]): 
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
                output += f"**Description**: {content}\n\n"
                
                if code_snippet:
                    output += "**Code Snippet**:\n"
                    output += "```html\n"
                    output += code_snippet + "\n"
                    output += "```\n"
                else:
                    # Fallback for old/text chunks
                    output += "**Content**:\n"
                    output += "```" + (meta.get("language", "") or "") + "\n"
                    output += content + "\n"
                    output += "```\n"
                
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
