import pytest


@pytest.fixture(autouse=True)
def no_real_llm_calls(monkeypatch):
    """Tests must never call the Claude API (cost, flakiness). Tests that need the AI pass a fake client."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CHANGESIGNAL_LANG", raising=False)
