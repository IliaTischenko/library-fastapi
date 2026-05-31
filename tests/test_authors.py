from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author
from app.schemas import AuthorResponse


@pytest_asyncio.fixture(scope="function")
async def create_authors(get_test_db_session: AsyncSession) -> AsyncGenerator[List[Author], None]:
    fixed_authors = [
        Author(full_name="a1", country="c1", birth_date=date(1978, 5,10)),
        Author(full_name="a2", country="c2", birth_date=date(1978, 5, 10)),
        Author(full_name="a3", country="c1", birth_date=date(1978, 5, 10))
    ]


    for author in fixed_authors:
        get_test_db_session.add(author)


    await get_test_db_session.commit()

    for author in fixed_authors:
        await get_test_db_session.refresh(author)


    yield fixed_authors

    for author in fixed_authors:
        await get_test_db_session.delete(author)

    await get_test_db_session.commit()




@pytest.mark.parametrize(
    "filter_param, expected_names",
    [
        #1. без фильтров, все три автора
        ({},("a1", "a2", "a3")),
        #2.фильтр по имени, только 1
        ({"author_name": "a1"},("a1",)),
        #3.фильтр по стране, только 1,3
        ({"country": "c1"}, ("a1","a3",)),
        #.фильтр по имени и по стране, только 3
        ({"country": "c1", "author_name": "a3"}, ("a3",))
    ]
)


@pytest.mark.asyncio
async def test_get_authors_filtered(
        client: AsyncClient,
        filter_param: dict[str, str],
        expected_names: tuple[int],
        create_authors: list[Author]
):

    response = await client.get("/authors/", params=filter_param)
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data) == len(expected_names)



    received_names = sorted([author["full_name"] for author in response_data])
    expected_authors_name = sorted(
        author.full_name for author in create_authors if author.full_name in expected_names
    )

    assert received_names == expected_authors_name


@pytest.mark.asyncio
async def test_get_author_detail(
    client: AsyncClient,
    create_authors: list[Author],
    get_test_db_session: AsyncSession
):
    target_author = create_authors[0]


    response = await client.get(f"/authors/{target_author.id}")
    assert response.status_code == 200

    validate_data = AuthorResponse.model_validate(response.json())

    expected_data = {
        "id": target_author.id,
        "full_name": target_author.full_name,
        "country": target_author.country,
        "birth_date": target_author.birth_date
    }

    assert validate_data.model_dump() == expected_data

@pytest.mark.asyncio
async def test_get_author_detail_not_found(
    client: AsyncClient,
    create_authors: list[Author]
):
    response = await client.get(f"/authors/312423431")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_author_anonymous_return_401(client: AsyncClient, setup_auth):
    auth_behavior = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (Cookie missing/Token in blacklist)"
            )
    setup_auth(auth_behavior)
    response = await client.post("/authors/", data={})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_author_as_user_return_403(client: AsyncClient, setup_auth):
    auth_behavior = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient rights"
    )

    setup_auth(auth_behavior)
    response = await client.post("/authors/", data={})
    data = response.json()
    print(data['detail'])
    assert response.status_code == 403

