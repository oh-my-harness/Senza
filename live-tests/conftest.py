# live-tests conftest — provider fixtures for real LLM integration tests.
#
# Without a configured API key, live_provider triggers pytest.skip so the
# suite is runnable by anyone without paying/calling a real endpoint.
import pytest
from base import provider_or_skip, providers_from_env


@pytest.fixture(scope="session")
def live_provider():
    """Yield a real provider (OMP DeepSeek by default), or skip when none set."""
    return provider_or_skip()


@pytest.fixture(scope="session")
def live_providers():
    """Yield all configured (name, provider) pairs (possibly empty)."""
    return providers_from_env()
