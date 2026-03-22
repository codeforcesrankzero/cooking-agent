from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from src.api import app


async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_query_returns_response():
    with patch("src.api.process_query", new=AsyncMock(return_value="тестовый ответ")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/query", json={"message": "курица", "chat_id": 1})
    assert resp.status_code == 200
    assert resp.json()["response"] == "тестовый ответ"


async def test_query_missing_message():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/query", json={})
    assert resp.status_code == 422
