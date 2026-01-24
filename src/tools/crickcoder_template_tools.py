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
        Automatically handles nested wrapper folders common in ZIP extracts.

        Args:
            template_id: The ID of the template (e.g., "tema607").
            asset_path: The relative path inside the template assets (e.g., "css", "js/main.js", "." for root).
            target_path: The destination path in your project (e.g., "public/css", "src/assets").
            
        Returns:
            Success or error message.
        """
        import shutil

        # Source Base: <SERVER_ROOT>/public/templates/<id>/assets
        source_base = os.path.join(self.server_root, "public", "templates", template_id, "assets")
        
        # Validation: check if template/assets exist
        if not os.path.exists(source_base):
             # Try identifying if template exists at all
             template_root = os.path.join(self.server_root, "public", "templates", template_id)
             if not os.path.exists(template_root):
                 return f"Error: Template '{template_id}' not found."
             # If template exists but no assets folder, maybe it's flat? 
             # For now, strictly require 'assets' folder to match architecture.
             return f"Error: No 'assets' folder found in template '{template_id}'."

        # SMART UNWRAP: Remove wrapper directories (e.g. "assets/MyThemeV1/...")
        # Often zip files extract into a single subdirectory. We want to skip that.
        # Heuristic: If there is exactly one item, it's a directory, and NOT a standard asset name.
        common_asset_names = {"css", "js", "img", "images", "fonts", "static", "media", "lib", "vendor", "assets"}
        
        # Limit recursion to avoid infinite loops (though unlikely with file system)
        unwrap_depth = 0
        while unwrap_depth < 3:
            try:
                items = os.listdir(source_base)
                if len(items) == 1:
                    single_item = items[0]
                    single_full = os.path.join(source_base, single_item)
                    
                    if os.path.isdir(single_full) and single_item.lower() not in common_asset_names:
                        # It looks like a wrapper (e.g. "material-dashboard-master") -> Unwrap it
                        source_base = single_full
                        unwrap_depth += 1
                        continue
            except Exception:
                pass
            break
        
        # Handle root access vs specific path
        if asset_path == "." or asset_path == "/" or not asset_path:
             full_source = source_base
        else:
             full_source = os.path.join(source_base, asset_path)

        # Target: Relative to Project Root (not CWD)
        if os.path.isabs(target_path):
            full_target = target_path
        else:
            full_target = os.path.join(self.project_root, target_path)

        # Smart Path Resolution (Standard Search)
        # If the specific asset requested (e.g. "css") isn't at the calculated root, search for it.
        if not os.path.exists(full_source):
            # Check recursively in subfolders
            found_smart = False
            for root, dirs, files in os.walk(source_base):
                # Check dirs
                if os.path.basename(asset_path) in dirs:
                     potential = os.path.join(root, os.path.basename(asset_path))
                     # Verify it matches the suffix requested to avoid partial matches if complex
                     # simplistic check:
                     full_source = potential
                     found_smart = True
                     break
                # Check files
                if os.path.basename(asset_path) in files:
                     potential = os.path.join(root, os.path.basename(asset_path))
                     full_source = potential
                     found_smart = True
                     break
            
            if not found_smart:
                # Generate a helpful directory listing
                try:
                    available = []
                    for root, dirs, files in os.walk(source_base):
                        for d in dirs:
                            rel = os.path.relpath(os.path.join(root, d), source_base)
                            if len(available) < 15: available.append(f"{rel}/")
                        for f in files:
                            rel = os.path.relpath(os.path.join(root, f), source_base)
                            if len(available) < 15: available.append(rel)
                    listing = ", ".join(available)
                except:
                    listing = "Error listing files"
                    
                return f"Error: Asset '{asset_path}' not found in {template_id}. Available in root: [{listing}...]"

        try:
            # Determine effective target
            effective_target = full_target
            
            if not os.path.isdir(full_source): # Source is FILE
                # If target looks like a DIR (no ext) or is existing DIR
                _, ext = os.path.splitext(full_target)
                if (not ext and not os.path.exists(full_target)) or os.path.isdir(full_target):
                    os.makedirs(full_target, exist_ok=True)
                    effective_target = os.path.join(full_target, os.path.basename(full_source))
                else:
                    os.makedirs(os.path.dirname(full_target), exist_ok=True)
            else: # Source is DIR
                 os.makedirs(os.path.dirname(full_target), exist_ok=True)

            message = ""
            if os.path.isdir(full_source):
                # Copy Directory
                # Note: copytree with dirs_exist_ok=True MERGES content.
                shutil.copytree(full_source, full_target, dirs_exist_ok=True)
                message = f"Directory '{asset_path}' (resolved to {os.path.basename(full_source)}) installed to '{target_path}'."
            else:
                # Copy File
                shutil.copy2(full_source, effective_target)
                message = f"File '{asset_path}' installed to '{effective_target}'."
            
            return f"SUCCESS: {message}"

        except Exception as e:
            return f"Error installing assets: {str(e)}"

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
            if not verbose:
                output += " (Compact Mode - Use `verbose=True` for full code)"
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
                
                if verbose:
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
                else:
                    # Compact: Truncate content/description
                    short_desc = (content[:300] + '...') if len(content) > 300 else content
                    output += f"**Snippet Preview**: {short_desc}\n"
                
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
