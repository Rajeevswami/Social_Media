"""Shared fixtures for the AI service test suite."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Deterministic settings + fresh provider/limiter caches per test."""
    monkeypatch.setenv("API_KEYS", API_KEY)
    monkeypatch.setenv("PROVIDER", "heuristic")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8000")

    from app.core.config import get_settings
    from app.providers.factory import reset_provider_cache

    get_settings.cache_clear()
    reset_provider_cache()
    yield
    get_settings.cache_clear()
    reset_provider_cache()


@pytest.fixture
def client():
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {"X-API-Key": API_KEY}
