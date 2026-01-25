from typing import List, Dict, Any, Optional
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

class ThemeChunker:
    """
    Optimized Chunker for Themes/Templates.
    - IGNORES: CSS, JS (too verbose), Images, Fonts.
    - FOCUS: HTML, PHP, JSX, TSX, View Logic (Structure).
    """
    def __init__(self):
        # Allow only structural/logic files
        self.ALLOWED_EXTENSIONS = {
            ".html", ".htm",
            ".php",
            ".tsx", ".ts",
            ".jsx", # .js is excluded as usually minified/vendor
            ".vue",
            ".py",
            ".rb",
            ".go",
            ".java",
            ".liquid", # Shopify
            ".erb", 
            ".ejs",
            ".handlebars", ".hbs"
        }
        
        # Explicitly Ignore (just for clarity, though strict allow-list covers it)
        # .css, .scss, .less, .js, .json, .svg, .xml, .txt, .md

        # Map for splitter language (if applicable)
        self.LANG_MAP = {
            ".html": Language.HTML,
            ".htm": Language.HTML,
            ".php": Language.PHP,
            ".tsx": Language.TS,
            ".ts": Language.TS,
            ".jsx": Language.JS, # Treat JSX as JS for splitting
            ".vue": Language.HTML, # Vue often HTML-like
            ".py": Language.PYTHON,
            ".go": Language.GO,
            ".java": Language.JAVA,
            ".cpp": Language.CPP,
        }

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ">", " ", ""]
        )

    def _get_splitter(self, filename: str):
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.LANG_MAP:
            return RecursiveCharacterTextSplitter.from_language(
                language=self.LANG_MAP[ext],
                chunk_size=4000, # Themes need smaller chunks than raw code
                chunk_overlap=200
            )
        return self.splitter

    def chunk_content(self, content: str, rel_path: str) -> List[Document]:
        ext = os.path.splitext(rel_path)[1].lower()
        
        # 1. Check Allow List
        if ext not in self.ALLOWED_EXTENSIONS:
            return [] # Skip file completely
            
        # 2. Split
        splitter = self._get_splitter(rel_path)
        try:
            return splitter.create_documents([content])
        except:
             return self.splitter.create_documents([content])
