from typing import List, Dict, Any, Optional
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

class AdaptiveChunker:
    def __init__(self, small_file_threshold: int = 30000):
        self.SMALL_FILE_THRESHOLD = small_file_threshold
        
        self.LANG_MAP = {
            ".py": Language.PYTHON,
            ".js": Language.JS,
            ".jsx": Language.JS,
            ".ts": Language.TS, 
            ".tsx": Language.TS,
            ".java": Language.JAVA,
            ".go": Language.GO,
            ".rs": Language.RUST,
            ".cpp": Language.CPP, 
            ".c": Language.CPP,
            ".php": Language.PHP,
            ".html": Language.HTML,
            ".css": Language.HTML
        }

        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ">", " ", ""]
        )

    def _get_splitter(self, filename: str):
        """Helper to choose the correct splitter based on extension."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.LANG_MAP:
            return RecursiveCharacterTextSplitter.from_language(
                language=self.LANG_MAP[ext],
                chunk_size=30000,
                chunk_overlap=2000
            )
        return self.fallback_splitter

    def chunk_content(self, content: str, rel_path: str) -> List[Document]:
        """
        Adaptively chunks content based on size and file type.
        Returns a list of Documents.
        """
        file_len = len(content)
        docs = []

        if file_len < self.SMALL_FILE_THRESHOLD:
            # Small file -> 1 Single Chunk
            docs = [Document(page_content=content)]
        else:
            # Large file -> Intelligent Split
            splitter = self._get_splitter(rel_path)
            try: 
                docs = splitter.create_documents([content])
            except Exception: 
                docs = self.fallback_splitter.create_documents([content])
        
        return docs
