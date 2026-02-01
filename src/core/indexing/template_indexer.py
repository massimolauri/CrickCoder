import os
import shutil
import zipfile
import glob
import time
import json
import logging
from typing import Generator, Dict, Any, Optional

# --- Agno Imports ---
from agno.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb, SearchType
from src.core.storage.embedder import get_shared_embedder

# --- Core Imports ---
from src.core.indexing.chunker import AdaptiveChunker
from src.core.indexing.theme_chunker import ThemeChunker
from src.models import LLMSettings

logger = logging.getLogger("TemplateIndexer")

class TemplateIndexer:
    def __init__(self, project_root: str, llm_settings: Optional[LLMSettings] = None):
        self.project_root = project_root
        self.llm_settings = llm_settings
        
        # GLOBAL PATH: ~/.crickcoder (User Home Directory)
        # Used for persistent internal data (Themes, Knowledge Base) across all projects.
        self.global_crick_dir = os.path.join(os.path.expanduser("~"), ".crickcoder")
        
        self.knowledge_base_dir = os.path.join(self.global_crick_dir, "knowledge_base")
        self.public_templates_dir = os.path.join(self.global_crick_dir, "public", "templates")
        
        # Ensure directories exist
        os.makedirs(self.knowledge_base_dir, exist_ok=True)
        os.makedirs(self.public_templates_dir, exist_ok=True)

        # Use ThemeChunker for smart indexing of templates
        self.chunker = ThemeChunker()

        # Shared Embedder (Cached Singleton)
        self.embedder = get_shared_embedder()

    def process_template_zip(self, zip_path: str) -> Generator[Dict[str, Any], None, None]:
        """
        Processing flow for Template ZIPs:
        1. Extract to temp
        2. Find Manifest (Get Template ID)
        3. Extract Preview Image -> public/templates
        4. Index Content -> knowledge_base
        """
        
        temp_dir = os.path.join(self.project_root, ".temp_extract", f"ext_{int(time.time())}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            yield {"status": "extracting", "message": "Extracting ZIP file..."}
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # --- 1. Identify Template from Manifest ---
            manifest_files = glob.glob(os.path.join(temp_dir, "**/*.manifest"), recursive=True)
            if not manifest_files:
                raise ValueError("No .manifest file found in ZIP! Cannot identify template.")
            
            # Use filename as template_id (e.g. 'modern-dashboard.manifest' -> 'modern-dashboard')
            manifest_path = manifest_files[0]
            template_id = os.path.splitext(os.path.basename(manifest_path))[0]
            
            yield {"status": "validating", "message": f"Found template: {template_id}"}
            
            # --- 2. Handle Assets (Preview Image & Manifest) ---
            template_public_dir = os.path.join(self.public_templates_dir, template_id)
            os.makedirs(template_public_dir, exist_ok=True)

            # Copy Manifest json for metadata usage
            try:
                # Always save as 'manifest.json' regardless of input name
                shutil.copy2(manifest_path, os.path.join(template_public_dir, "manifest.json"))
            except Exception as e:
                logger.warning(f"Could not save manifest: {e}")

            # Look for theme_screen.png anywhere
            preview_files = glob.glob(os.path.join(temp_dir, "**", "theme_screen.png"), recursive=True)
            
            has_preview = False

            if preview_files:
                # Copy to public public/templates/<id>/theme_screen.png
                shutil.copy2(preview_files[0], os.path.join(template_public_dir, "theme_screen.png"))
                has_preview = True
                yield {"status": "validating", "message": "Preview image extracted."}
            else:
                yield {"status": "warning", "message": "No theme_screen.png found."}
                yield {"status": "warning", "message": "No theme_screen.png found."}

            # --- 2b. Preserve Static Assets (CSS, JS, Fonts, Img) ---
            # Copy full content to public/templates/<id>/assets for Coder access
            assets_dir = os.path.join(template_public_dir, "assets")
            if os.path.exists(assets_dir):
                shutil.rmtree(assets_dir) # Clean if re-installing
            
            # Copytree requires destination to NOT exist (usually), or ignore errors
            # Since we just cleaned it or it's new, we can copy.
            try:
                shutil.copytree(temp_dir, assets_dir)
                yield {"status": "copying", "message": f"Assets archived to {assets_dir}"}
            except Exception as e:
                logger.error(f"Failed to copy assets: {e}")
                yield {"status": "warning", "message": "Failed to preserve static assets."}

            # --- 3. Setup Vector DB for this Template ---
            # DB Path: <project_root>/knowledge_base/templates.lance (One DB for all templates? Or separate?)
            # Plan says: separate LanceDB instance stored locally.
            # "Il nome della tabella è uguale al nome di un file manifest"
            # Let's use a shared DB for all templates, but different TABLES.
            # DB Path: knowledge_base/templates_db
            
            db_path = os.path.join(self.knowledge_base_dir, "templates_db")
            vector_db = LanceDb(
                table_name=template_id, # Table Name = Template ID
                uri=db_path,
                embedder=self.embedder,
                search_type=SearchType.hybrid,
                reranker=False
            )
            
            # Clean existing if needed
            if vector_db.exists():
                vector_db.drop() # Overwrite template if re-uploaded
            
            knowledge = Knowledge(
                name=template_id,
                vector_db=vector_db
            )

            # --- 4. Indexing Content (AI-DRIVEN) ---
            # Instead of naive chunking, we use UIArchitectAgent + BeautifulSoup
            
            # Import dependencies
            # Wrapper to handle Pydantic Response
            from bs4 import BeautifulSoup
            from agno.agent import Agent
            from src.core.config.factory_models import build_model_for_runtime

            # Initialize Architect
            if not self.llm_settings:
                # Fallback or error? For now, we assume settings are passed.
                # If missing, we might need a default config or raise error.
                yield {"status": "error", "message": "LLM Settings missing for AI Analysis."}
                return

            model = build_model_for_runtime(
                 provider=self.llm_settings.provider,
                 model_id=self.llm_settings.model_id,
                 temperature=0.1,
                 api_key=self.llm_settings.api_key,
                 base_url=self.llm_settings.base_url
            )

            ui_architect_agent = Agent(
                model=model,
                description="UI Architect",
                instructions="You are an expert UI Architect. Your goal is to analyze HTML and extract components with their categories, names, and selectors. Output valid JSON.",
                markdown=True
            )
            
            # Wrapper to handle Pydantic Response
            def analyze_html_wrapper(html_content):
                try:
                    response = ui_architect_agent.run(
                       f"Analyze the following HTML code and extract user interface components:\n\n```html\n{html_content[:50000]}\n```"
                    )
                    # With response_model, content should be the Pydantic object
                    result = response.content
                    if hasattr(result, "components"):
                        return result.components
                    return []
                except Exception as e:
                    logger.error(f"Agent Analysis Failed: {e}")
                    return []

            files_to_index = []
            
            # Scan all files - FOCUS ON HTML
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, temp_dir).replace("\\", "/")
                    
                    # AI Analysis only for HTML files
                    if file.lower().endswith((".html", ".htm")):
                         files_to_index.append((full_path, rel_path))
            
            total_files = len(files_to_index)
            yield {"status": "indexing", "total": total_files, "current": 0, "message": "Starting AI Analysis..."}

            batch_docs = []
            
            for i, (full_path, rel_path) in enumerate(files_to_index):
                try:
                    yield {"status": "indexing", "total": total_files, "current": i+1, "message": f"Analyzing UI: {rel_path}..."}
                    
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # 1. PRE-SCAN: Extract Assets (The "Menu")
                    soup = BeautifulSoup(content, "html.parser")
                    assets_found = []
                    # Find CSS
                    for link in soup.find_all('link', rel='stylesheet'):
                        href = link.get('href')
                        if href: assets_found.append(href)
                    # Find JS
                    for script in soup.find_all('script'):
                        src = script.get('src')
                        if src: assets_found.append(src)
                    
                    assets_json_string = json.dumps(list(set(assets_found)), indent=2)

                    # 2. SEQUENCE: AI Analysis with Context
                    prompt_msg = (
                        f"### AVAILABLE ASSETS (The 'Pantry'):\n{assets_json_string}\n\n"
                        f"### HTML CONTENT TO ANALYZE:\n```html\n{content[:50000]}\n```"
                    )

                    try:
                        response = ui_architect_agent.run(prompt_msg)
                        # Agno with response_model returns the object directly in content usually, 
                        # or we access it depending on version. 
                        # Assuming response.content IS the AnalysisResult based on previous steps.
                        result = response.content
                        components_list = result.components if hasattr(result, "components") else []
                    except Exception as e:
                        logger.error(f"Agent Run Failed: {e}")
                        components_list = []
                    
                    # 3. EXTRACTION & INDEXING
                    for comp in components_list:
                        selector = comp.selector
                        if not selector: continue

                        element = soup.select_one(selector)
                        
                        if element:
                            raw_code = str(element)
                            
                            # ID Unique for Vector DB
                            chunk_id = f"{template_id}#{rel_path}#{selector}"
                            
                            batch_docs.append({
                                "name": chunk_id,
                                "text_content": comp.description, # Semantic Description
                                "metadata": {
                                    "template_id": template_id,
                                    "path": rel_path,
                                    "filename": os.path.basename(rel_path),
                                    "component_name": comp.name,
                                    "category": comp.category,
                                    "requires_js": comp.requires_js,
                                    "dependencies": json.dumps(comp.dependencies), # Store deps!
                                    "selector": selector,
                                    "code_snippet": raw_code,
                                    "is_template": True
                                }
                            })
                            logger.info(f"      [OK] Extracted: {comp.name} ({comp.category}) | Deps: {len(comp.dependencies)}")

                except Exception as e:
                    logger.error(f"Error analyzing {rel_path}: {e}")

            # Final Batch insert
            if batch_docs:
                knowledge.add_contents(batch_docs)

            yield {
                "status": "complete", 
                "template_id": template_id,
                "preview_url": f"/public/templates/{template_id}/theme_screen.png" if has_preview else None,
                "message": "Template installed successfully!"
            }

        except Exception as e:
            logger.error(f"Template Processing Error: {e}", exc_info=True)
            yield {"status": "error", "message": str(e)}
            
        finally:
            # Cleanup Temp
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _is_binary_file(self, filepath):
        try:
            with open(filepath, 'rb') as f: return b'\0' in f.read(1024)
        except: return True

    def _format_repomix_style(self, path, content):
        ext = os.path.splitext(path)[1]
        return f"""<file path="{path}" extension="{ext}">\n{content}\n</file>"""
