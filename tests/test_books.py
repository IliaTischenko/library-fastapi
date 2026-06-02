from datetime import date
from typing import AsyncGenerator, Callable, Any, NoReturn
import pytest
import pytest_asyncio

from fastapi import HTTPException, status
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author, Book
from app.schemas import BookResponse


@pytest_asyncio.fixture(scope="function")
async def clear_books(get_test_db_session: AsyncSession) -> AsyncGenerator[None, None]:
    yield
    await get_test_db_session.execute(delete(Book))
    await get_test_db_session.execute(delete(Author))
    await get_test_db_session.commit()


@pytest_asyncio.fixture(scope="function")
async def create_books(
        get_test_db_session: AsyncSession,
        clear_books: None
) -> list[Book]:
    author_1 = Author(full_name="a1", country="c1", birth_date=date(1978, 5,10))
    author_2 = Author(full_name="a2", country="c1", birth_date=date(1978, 5,10))

    get_test_db_session.add(author_1)
    get_test_db_session.add(author_2)

    await get_test_db_session.commit()
    await get_test_db_session.refresh(author_1)
    await get_test_db_session.refresh(author_2)


    book_1 = Book(title="b1", author_id=author_1.id, pages=10)
    book_2 = Book(title="b2", author_id=author_1.id, pages=10)
    book_3 = Book(title="b3", author_id=author_2.id, pages=10)

    created_books = [book_1, book_2, book_3]
    book_1.author = author_1
    book_2.author = author_1
    book_3.author = author_2

    for book in created_books:
        get_test_db_session.add(book)

    await get_test_db_session.commit()

    stmt = (
        select(Book)
        .where(Book.id.in_([b.id for b in created_books]))
        .options(selectinload(Book.author))
    )

    result = await get_test_db_session.execute(stmt)
    refreshed_books = result.scalars().all()

    return list(refreshed_books)



@pytest.mark.parametrize(
    "filter_params, expected_titles",
    [
        #Без фильтров
        ({}, ("b1","b2","b3")),
        #Фильтр по автору
        ({"author_name": "a1"}, ("b1","b2",)),
        #Фильтр по названию книги
        ({"book_title": "b1"}, ("b1",)),
        #Фильтр по названию книги и автору
        ({"author_name": "a1", "book_title": "b1"}, ("b1",))
    ]
)
@pytest.mark.asyncio
async def test_get_book_filtered_200(
        client: AsyncClient,
        create_books: list[Book],
        filter_params: dict[str, str],
        expected_titles: tuple[str]
):
    response = await client.get("/books/", params=filter_params)
    assert response.status_code == 200

    response_data = response.json()

    assert len(response_data) == len(expected_titles)


    response_titles = sorted([book['title'] for book in response_data])
    assert sorted(expected_titles) == response_titles


@pytest.mark.asyncio
async def test_get_book_detail_200(
        client: AsyncClient,
        create_books: list[Book]
):
    target = create_books[0]
    target_id = target.id

    response = await client.get(f"/books/{target_id}")

    assert response.status_code == 200

    response_data = BookResponse.model_validate(response.json())

    expected_data = {
        "id": target_id,
        "title": target.title,
        "pages": target.pages,
        "author": {
            "id": target.author.id,
            "full_name": target.author.full_name,
            "country": target.author.country,
            "birth_date": target.author.birth_date
        }
    }
    assert expected_data == response_data.model_dump()



@pytest.mark.asyncio
async def create_book_anonymous_return_401(
        client: AsyncClient,
        setup_auth: Callable[[HTTPException | dict[str, Any]], dict[str, Any] | NoReturn],
):
    auth_behavior = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated (Cookie missing/Token in blacklist)"
    )
    setup_auth(auth_behavior)

    response = await client.post("/books/", json=())

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_author_as_user_return_403(
        client: AsyncClient,
        setup_auth: Callable[[HTTPException | dict[str, Any]], dict[str, Any] | NoReturn],
    ):
    auth_behavior = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient rights"
    )
    setup_auth(auth_behavior)

    response = await client.post("/books/", json=())

    assert response.status_code == 403



