"""Keep offline tests deterministic when a developer has a live local .env."""

from collections.abc import Generator

import pytest

from api.config import get_settings


@pytest.fixture(autouse=True)
def isolate_test_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Prevent developer credentials from turning unit tests into live requests."""

    monkeypatch.setenv("DEMO_MODE", "offline")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("EBAY_CLIENT_ID", "")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
