import httpx
from config.settings import CLINICAL_API_BASE_URL

REQUEST_TIMEOUT = httpx.Timeout(90.0, connect=10.0)

def _api_error(exc: Exception, path: str) -> dict:
    """Return tool-safe errors so ADK does not cancel the agent node."""
    error = {
        "error": type(exc).__name__,
        "message": str(exc),
        "path": path,
        "retryable": isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)),
    }
    if isinstance(exc, httpx.HTTPStatusError):
        error["status_code"] = exc.response.status_code
        error["response"] = exc.response.text[:500]
    return error

def _request(method: str, path: str, **kwargs) -> dict:
    url = f"{CLINICAL_API_BASE_URL.rstrip('/')}{path}"
    try:
        response = httpx.request(
            method,
            url,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return _api_error(exc, path)
