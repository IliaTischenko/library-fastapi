import time

import pytest
import jwt
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

from app.models import User


@pytest.mark.asyncio
async def test_login_success_200(
        client: AsyncClient,
        create_users: list[User]
):
    login_payload = {
        "username": "username1",
        "password": "correct_password"
    }
    client.cookies.delete("access_token")

    response = await client.post("/auth/login", json=login_payload)

    assert response.status_code == 200

    token = response.cookies.get("access_token")
    assert token is not None

    assert response.json()['detail'] == "Login success"


@pytest.mark.parametrize(
    "invalid_payload",
    (
        #1 Неверно username
        {"username": "fake_username", "password": "correct_password"},
        #1 Неверный password
        {"username": "username1", "password": "fake_pass"}
    )
)
@pytest.mark.asyncio
async def test_login_invalid_payloads_400(
        client: AsyncClient,
        create_users: list[User],
        invalid_payload: dict[str]
):
    client.cookies.delete("access_token")

    response = await client.post("/auth/login", json=invalid_payload)

    assert response.status_code == 401

    token = client.cookies.get("access_token")
    assert token is None

    assert response.json()['detail'] == "Wrong username or password"

@pytest.mark.asyncio
async def test_logout_200(
        client: AsyncClient,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": int(time.time()) + 86000, "token_str": "ac"}
    setup_auth(auth_behavior)

    client.cookies.set("access_token", "token")

    response = await client.post("/auth/logout", json={})

    assert response.status_code == 200
    assert response.json()['detail'] == "Logout success"

    assert "access_token" in response.cookies
    assert response.cookies.get("access_token") == ""


@pytest.mark.parametrize(
    "type_error, error_message",
    (
        (jwt.InvalidTokenError(), "Invalid session token"),
        (jwt.ExpiredSignatureError(), "Session expired")
    )
)
@pytest.mark.asyncio
async def test_expire_invalid_token_401(
        client: AsyncClient,
        type_error: jwt.exceptions,
        error_message: str
):
    client.cookies.set("access_token", "some_fake_token_string")

    with patch("app.auth_utils.jwt.decode") as mock_decode:
        mock_decode.side_effect = type_error

        response = await client.delete("/books/1")
        assert response.status_code == 401

        assert response.json()['detail'] == error_message

        mock_decode.assert_called_once()


@pytest.mark.asyncio
async def test_token_is_blacklisted_401(
        client: AsyncClient
):
    client.cookies.set("access_token", "some_fake_token_string")
    with patch("app.auth_utils.is_token_blacklisted", new_callable=AsyncMock) as mock_blacklist_check:
        mock_blacklist_check.return_value = True

        response = await client.delete("/users/1")

        assert response.status_code == 401

        assert response.json()['detail'] == "Session revoked. Please log in again. (Token is blacklisted)"

        mock_blacklist_check.assert_called_once_with("some_fake_token_string")

