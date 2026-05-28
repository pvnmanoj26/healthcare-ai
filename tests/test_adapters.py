from adapters.vertex_ai import _initialized as vertex_init
from adapters.anthropic import DEFAULT_MODEL

def test_adapters_imports():
    assert not vertex_init  # Starts uninitialized
    assert isinstance(DEFAULT_MODEL, str)
    print("test_adapters_imports passed!")

if __name__ == "__main__":
    test_adapters_imports()
    print("All adapter tests passed!")
