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
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# --- Core Imports ---
from src.core.chunker import AdaptiveChunker

logger = logging.getLogger("TemplateIndexer")

class TemplateIndexer:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.knowledge_base_dir = os.path.join(project_root, "knowledge_base")
        self.public_templates_dir = os.path.join(project_root, "public", "templates")
        
        # Ensure directories exist
        os.makedirs(self.knowledge_base_dir, exist_ok=True)
        os.makedirs(self.public_templates_dir, exist_ok=True)

        self.chunker = AdaptiveChunker()

        # Shared Embedder (Reuse logic from UniversalCodeIndexer if possible, else new instance)
        self.embedder = SentenceTransformerEmbedder(
            id="jinaai/jina-embeddings-v2-base-code",
            dimensions=768
        )

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

            # --- 4. Indexing Content ---
            files_to_index = []
            
            # Scan all files
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, temp_dir).replace("\\", "/")
                    
                    # Skip binaries, images, git, etc.
                    if self._is_binary_file(full_path) or file.endswith(".manifest"):
                        continue
                        
                    files_to_index.append((full_path, rel_path))

            total_files = len(files_to_index)
            yield {"status": "indexing", "total": total_files, "current": 0, "message": "Starting indexing..."}

            batch_size = 10
            batch_docs = []
            
            for i, (full_path, rel_path) in enumerate(files_to_index):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    if not content.strip(): continue

                    # Chunking
                    docs = self.chunker.chunk_content(content, rel_path)
                    
                    for idx, doc in enumerate(docs):
                        chunk_id = f"{template_id}#{rel_path}#{idx}"
                        rag_content = self._format_repomix_style(rel_path, doc.page_content)
                        
                        batch_docs.append({
                            "name": chunk_id,
                            "text_content": rag_content,
                            "metadata": {
                                "template_id": template_id,
                                "path": rel_path,
                                "chunk_index": idx,
                                "is_template": True
                            }
                        })
                        
                except Exception as e:
                    logger.error(f"Error reading {rel_path}: {e}")

                # Yield progress
                yield {"status": "indexing", "total": total_files, "current": i+1, "filename": rel_path}

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
