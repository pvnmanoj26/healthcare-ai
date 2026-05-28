import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import ANTHROPIC_API_KEY

# Lazy-loaded Anthropic client
_client = None
DEFAULT_MODEL = "claude-haiku-4-5"  # Default fallback model (Haiku)

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY must be set in settings.")
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def get_claude_response(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    model: str | None = None,
) -> str:
    """Send a message to Claude and get the text response."""
    client = get_client()
    selected_model = model or DEFAULT_MODEL
    
    response = client.messages.create(
        model=selected_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text
            
    return text.strip()
