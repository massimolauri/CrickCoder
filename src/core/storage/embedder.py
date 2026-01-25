import threading
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

# Global singleton instance
_shared_embedder = None
_embedder_lock = threading.Lock()

def get_shared_embedder() -> SentenceTransformerEmbedder:
    """
    Returns a shared singleton instance of the SentenceTransformerEmbedder.
    Ensures the heavy model is loaded only once per application lifecycle.
    """
    global _shared_embedder
    
    if _shared_embedder is None:
        with _embedder_lock:
            # Double-check locking pattern
            if _shared_embedder is None:
                # Use a standard, high-quality, lightweight code embedding model
                # jina-embeddings-v2-base-code supports 8k context length
                _shared_embedder = SentenceTransformerEmbedder(
                    id="jinaai/jina-embeddings-v2-base-code",
                    dimensions=768
                )
                
    return _shared_embedder
