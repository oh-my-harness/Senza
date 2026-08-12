import senza


def test_create_openai_provider():
    provider = senza.providers.openai(api_key="test-key")
    assert provider is not None
    assert type(provider).__name__ == "Provider"


def test_create_openai_provider_with_base_url():
    provider = senza.providers.openai(api_key="test-key", base_url="http://localhost:8080")
    assert provider is not None


def test_create_anthropic_provider():
    provider = senza.providers.anthropic(api_key="test-key")
    assert provider is not None
    assert type(provider).__name__ == "Provider"
