import pytest


@pytest.mark.anyio
async def test_create_author(client):

    response = await client.get("/authors/")

    assert response.status_code == 200
    assert isinstance(response.json(), list)