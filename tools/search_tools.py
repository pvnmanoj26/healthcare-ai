from adapters.cloud_run import _request

def _safe_limit(limit: int, default: int = 5, maximum: int = 10) -> int:
    try:
        return min(max(int(limit), 1), maximum)
    except (TypeError, ValueError):
        return default

def search_clinical_notes(query: str, top_k: int = 5) -> dict:
    """
    Semantic search over all indexed clinical notes.
    Use for finding notes about specific conditions or symptoms.
    """
    return _request("POST", "/search",
                    json={"query": query, "top_k": _safe_limit(top_k)})

def ask_clinical_question(question: str) -> dict:
    """
    Ask a clinical question using RAG over indexed notes.
    Best for cross-patient questions or protocol queries.
    """
    return _request("POST", "/ask", json={"query": question})
