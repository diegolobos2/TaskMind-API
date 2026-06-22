import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_notify():
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/notify",
            json={
                "recipient": "alumno@test.com",
                "message": "Nueva tarea creada",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["recipient"] == "alumno@test.com"