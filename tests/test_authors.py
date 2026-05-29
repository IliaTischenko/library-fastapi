from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author


@pytest_asyncio.fixture(scope="function")
async def create_authors(get_test_db_session: AsyncSession) -> list[Author]:
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

    return fixed_authors


@pytest.mark.parametrize(
    "filter_param, expected_authors_id",
    [
        #1. без фильтров, все три автора
        ({},(1, 2, 3)),
        #2.фильтр по имени, только 1
        ({"author_name": "a1"},(1,)),
        #3.фильтр по стране, только 1,3
        #({"country": "c1"}, (1,3)),
    ]
)


@pytest.mark.anyio
async def test_get_authors_filtered(
        client: AsyncClient,
        filter_param: dict[str, str],
        expected_authors_id:int,
        create_authors: list[Author]
):
    response = await client.get("/authors/")
    #response = await client.get("/authors/", params=filter_param)
    assert response.status_code == 200