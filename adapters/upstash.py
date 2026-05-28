from upstash_vector import Index
from config.settings import UPSTASH_VECTOR_REST_URL, UPSTASH_VECTOR_REST_TOKEN

# Lazy-loaded vector index
_index = None

def get_index() -> Index:
    global _index
    if _index is None:
        if not UPSTASH_VECTOR_REST_URL or not UPSTASH_VECTOR_REST_TOKEN:
            raise ValueError(
                "UPSTASH_VECTOR_REST_URL and UPSTASH_VECTOR_REST_TOKEN must be set in settings."
            )
        _index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)
    return _index

def upsert_vectors(vectors: list[dict]) -> dict:
    """
    Upsert vectors to Upstash Vector Index.
    vectors: list of dicts like:
        {
            "id": str,
            "vector": list[float],
            "data": str,
            "metadata": dict
        }
    """
    index = get_index()
    return index.upsert(vectors=vectors)

def query_vectors(vector: list[float], top_k: int = 5) -> list:
    """
    Query vector index. Returns raw results containing id, score, data, metadata.
    """
    index = get_index()
    return index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
        include_data=True
    )

def get_vector_count() -> int:
    """Return the total number of vectors in the index."""
    try:
        index = get_index()
        return index.info().vector_count
    except Exception:
        return 0
