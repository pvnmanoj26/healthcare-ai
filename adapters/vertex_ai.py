import vertexai
from vertexai.language_models import TextEmbeddingModel
from config.settings import GCP_PROJECT_ID

# Initialize Vertex AI lazily
_initialized = False
_embedder = None

def _ensure_initialized():
    global _initialized, _embedder
    if not _initialized:
        project = GCP_PROJECT_ID or "healthcare-ai-manoj"
        location = "us-central1"  # Default fallback location
        vertexai.init(project=project, location=location)
        _embedder = TextEmbeddingModel.from_pretrained("text-embedding-004")
        _initialized = True

def get_embedding(text: str) -> list[float]:
    """Get embedding vector using Vertex AI text-embedding-004."""
    _ensure_initialized()
    # Truncate to safety limit (3000 chars)
    result = _embedder.get_embeddings([text[:3000]])
    return result[0].values
