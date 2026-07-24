import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_user(client: AsyncClient):
    payload = {
        "email": "test@samaritan.io",
        "username": "testuser",
        "password": "StrongPassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    if response.status_code != 201:
        print("ERROR RESPONSE:", response.json())
    assert response.status_code == 201
    data = response.json()
    assert "data" in data
    assert data["data"]["email"] == "test@samaritan.io"
    assert data["data"]["username"] == "testuser"
    assert "id" in data["data"]


async def test_login_user(client: AsyncClient):
    # Register first
    payload = {
        "email": "login@samaritan.io",
        "username": "loginuser",
        "password": "StrongPassword123!",
    }
    await client.post("/api/v1/auth/register", json=payload)

    # Login
    login_payload = {
        "email": "login@samaritan.io",
        "password": "StrongPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]
