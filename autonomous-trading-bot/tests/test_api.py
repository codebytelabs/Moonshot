"""
Unit tests for FastAPI API endpoints.
"""
import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from src.api import create_app


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    bot_state = {"mode": "paper"}
    return create_app(bot_state)


class TestAPI:
    @pytest.mark.asyncio
    async def test_health(self, app):
        """GET /health returns ok."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_status(self, app):
        """GET /status returns mode."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_positions_empty(self, app):
        """GET /positions returns empty list when no PM."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/positions")
        assert resp.status_code == 200
        assert resp.json()["positions"] == []

    @pytest.mark.asyncio
    async def test_trades_empty(self, app):
        """GET /trades returns empty when no store."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/trades")
        assert resp.status_code == 200
        assert resp.json()["trades"] == []

    @pytest.mark.asyncio
    async def test_metrics(self, app):
        """GET /metrics returns Prometheus text."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/metrics")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_no_openrouter(self, app):
        """POST /chat without OpenRouter → fallback message."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/chat", json={"message": "hello"})
        assert resp.status_code == 200
        assert "not available" in resp.json()["reply"].lower() or "not configured" in resp.json()["reply"].lower()
