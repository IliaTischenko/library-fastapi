from datetime import date
from typing import AsyncGenerator, Any
import pytest
import pytest_asyncio

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
async def fixed_books(
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
        fixed_books: list[Book],
        filter_params: dict[str, str],
        expected_titles: tuple[str]
):
    response = await client.get("/books/", params=filter_params)
    assert response.status_code == 200

    list_response_validate = [BookResponse.model_validate(b) for b in response.json()]

    assert len(expected_titles) == len(list_response_validate)

    sorted_response_titles = sorted([b.title for b in list_response_validate])
    sorted_expected_titles = sorted(expected_titles)

    assert sorted_expected_titles == sorted_response_titles

    expected_books_from_db = [b for b in fixed_books if b.title in expected_titles]

    expected_books_from_db.sort(key=lambda b: b.title)
    list_response_validate.sort(key=lambda b: b.title)

    for resp_book, db_book in zip(list_response_validate, expected_books_from_db):
        assert resp_book.id == db_book.id
        assert resp_book.title == db_book.title
        assert resp_book.pages == db_book.pages
        assert resp_book.author.id == db_book.author.id


@pytest.mark.asyncio
async def test_get_book_detail_200(
        client: AsyncClient,
        fixed_books: list[Book]
):
    target = fixed_books[0]
    target_id = target.id

    response = await client.get(f"/books/{target_id}")

    assert response.status_code == 200

    response_data = BookResponse.model_validate(response.json())

    assert BookResponse.model_validate(target) == response_data


@pytest.mark.asyncio
async def create_book_anonymous_return_401(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession
):

    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.post("/books/", json=())

    assert response.status_code == 401

    result = await get_test_db_session.execute(select(Book))
    existing_books = result.scalars().all()

    assert len(existing_books) == 0


@pytest.mark.asyncio
async def test_create_book_as_user_return_403(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "At"}
    setup_auth(auth_behavior)

    response = await client.post("/books/", json=())

    assert response.status_code == 403

    result = await get_test_db_session.execute(select(Book))
    existing_books = result.scalars().all()

    assert len(existing_books) == 0


@pytest.mark.parametrize(
    "invalid_payload, expected_status, expected_error_loc, expected_error_type",
    (
        #Несуществующий автор
        ({"title": "b1", "author_id": 999999, "pages": 12}, 404, "", ""),
        #Пустой title
        ({"title": "", "author_id": 1, "pages": 12}, 422, "title", "string_too_short"),
        #Некорректный title >30
        ({"title": "b" * 40, "author_id": 1, "pages": 12}, 422, "title", "string_too_long"),
        #Пустой author_id
        ({"title": "b1", "author_id": "", "pages": 12}, 422, "author_id", "int_parsing"),
        #Некорректный author_id < 0
        ({"title": "b1", "author_id": -1, "pages": 12}, 422, "author_id", "greater_than_equal"),
        #Некорректный pages < 1
        ({"title": "b1", "author_id": 1, "pages": -12}, 422, "pages", "greater_than_equal"),
        #Отсутствует поле title
        ({"author_id": 1, "pages": 12}, 422, "title", "missing"),
        # Отсутствует поле author_id
        ({"title": "b1", "pages": -12}, 422, "author_id", "missing"),
        # Отсутствует поле pages
        ({"title": "b1", "author_id": 1}, 422, "pages", "missing"),
    )
)
@pytest.mark.asyncio
async def test_create_book_invalid_payloads_404_422(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession,
        invalid_payload: dict[str, Any],
        expected_status: int,
        expected_error_loc: list[str],
        expected_error_type: list[str]
):
    auth_behavior = {"id": 1, "role": "admin", "exp":1, "token_str": "at"}
    setup_auth(auth_behavior)

    response = await client.post("/books/", json=invalid_payload)

    assert response.status_code == expected_status

    if expected_status == 422:
        error_response_data = response.json()['detail'][0]
        assert expected_error_loc in error_response_data['loc'] and error_response_data['type'] == expected_error_type


@pytest.mark.asyncio
async def test_create_book_success_201(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession
):
    auth_behavior = {"id": 1, "role": "admin", "exp":1, "token_str": "at"}
    setup_auth(auth_behavior)

    author_db = Author(full_name="a1", country="c1", birth_date=date(1999, 10, 11))
    get_test_db_session.add(author_db)
    await get_test_db_session.commit()
    await get_test_db_session.refresh(author_db)

    book_payloads = {
        "title": "b1",
        "author_id": author_db.id,
        "pages": 12,
    }

    response = await client.post("/books/", json=book_payloads)

    assert response.status_code == 201

    response_validated_data = BookResponse.model_validate(response.json())

    assert book_payloads['title'] == response_validated_data.title
    assert book_payloads['author_id'] == response_validated_data.author.id
    assert book_payloads['pages'] == response_validated_data.pages

    get_test_db_session.expire_all()

    query = select(Book).where(Book.id == response_validated_data.id).options(selectinload(Book.author))
    result = await get_test_db_session.execute(query)
    db_book = result.scalar_one_or_none()
    assert db_book is not None

    book_db_validated = BookResponse.model_validate(db_book)

    assert book_db_validated == response_validated_data


@pytest.mark.asyncio
async def test_put_book_anonymous_return_401(
        client: AsyncClient,
        fixed_books: list[Book],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    old_book = {
        "id": fixed_books[0].id,
        "author_id": fixed_books[0].author_id,
        "title": fixed_books[0].title,
        "pages": fixed_books[0].pages
    }

    response = await client.put(f"/books/{old_book['id']}", json={})

    assert response.status_code == 401

    get_test_db_session.expire_all()
    existing_book = await get_test_db_session.get(Book, old_book['id'])

    assert existing_book.id == old_book['id']
    assert existing_book.author_id == old_book['author_id']
    assert existing_book.title == old_book['title']
    assert existing_book.pages == old_book['pages']


@pytest.mark.asyncio
async def test_put_book_as_user_return_403(
        client: AsyncClient,
        fixed_books: list[Book],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    old_book = {
        "id": fixed_books[0].id,
        "author_id": fixed_books[0].author_id,
        "title": fixed_books[0].title,
        "pages": fixed_books[0].pages
    }

    response = await client.put(f"/books/{old_book['id']}", json={})
    assert response.status_code == 403

    get_test_db_session.expire_all()
    existing_book = await get_test_db_session.get(Book, old_book['id'])

    assert existing_book.id == old_book['id']
    assert existing_book.author_id == old_book['author_id']
    assert existing_book.title == old_book['title']
    assert existing_book.pages == old_book['pages']


@pytest.mark.asyncio
async def test_put_book_success_201(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
        fixed_books: list[Book]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)
    target_id = fixed_books[0].id
    new_author_id = fixed_books[2].author_id

    book_payload = {
        "title": "new_title_book",
        "pages": 1234,
        "author_id": new_author_id
    }

    response = await client.put(f"/books/{target_id}", json=book_payload)

    assert response.status_code == 200

    response_validated = BookResponse.model_validate(response.json())
    assert book_payload['title'] == response_validated.title
    assert book_payload['pages'] == response_validated.pages
    assert new_author_id == response_validated.author.id

    get_test_db_session.expire_all()

    query = select(Book).where(Book.id == target_id).options(selectinload(Book.author))
    result = await get_test_db_session.execute(query)
    db_book = result.scalar_one_or_none()
    assert db_book is not None

    db_book_validated = BookResponse.model_validate(db_book)

    assert db_book_validated == response_validated


@pytest.mark.parametrize(
    "exist_book_id, invalid_put, expected_status, expected_error_loc, expected_error_type",
    (
        # Несуществующий id_book
        (False, {"title": "b1", "author_id": 999999, "pages": 12}, 404, "", ""),
        # Несуществующий автор
        (True, {"title": "b1", "author_id": 999999, "pages": 12}, 404, "", ""),
        # Отсутствует title
        (True, {"title": "", "author_id": 1, "pages": 12}, 422, "title", "string_too_short"),
        # Некорректный title >30
        (True, {"title": "b" * 40, "author_id": 1, "pages": 12}, 422, "title", "string_too_long"),
        # Отсутствует author_id
        (True, {"title": "b33", "author_id": "", "pages": 12}, 422, "author_id", "int_parsing"),
        # Некорректный author_id < 0
        (True, {"title": "b4", "author_id": -1, "pages": 12}, 422, "author_id", "greater_than_equal"),
        # Некорректный pages < 1
        (True, {"title": "b5", "author_id": 1, "pages": -12}, 422, "pages", "greater_than_equal"),
        # Отсутствует поле title
        (True, {"author_id": 1, "pages": 12}, 422, "title", "missing"),
        # Отсутствует поле author_id
        (True, {"title": "b1", "pages": -12}, 422, "author_id", "missing"),
        # Отсутствует поле pages
        (True, {"title": "b1", "author_id": 1}, 422, "pages", "missing"),
    )
)
@pytest.mark.asyncio
async def test_put_book_invalid_payloads_422_404(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
        fixed_books: list[Book],
        exist_book_id: bool,
        invalid_put: dict[str, Any],
        expected_status: int,
        expected_error_loc: str,
        expected_error_type: str
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    if exist_book_id:
        target_id = fixed_books[0].id
    else:
        target_id = 99999

    response = await client.put(f"/books/{target_id}", json=invalid_put)
    assert response.status_code == expected_status
    if expected_status == 422:
        error_data = response.json()['detail'][0]
        assert expected_error_loc in error_data['loc'] and expected_error_type == error_data['type']


@pytest.mark.asyncio
async def test_patch_book_anonymous_return_401(
        client: AsyncClient,
        fixed_books: list[Book],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    old_book = {
        "id": fixed_books[0].id,
        "author_id": fixed_books[0].author_id,
        "title": fixed_books[0].title,
        "pages": fixed_books[0].pages
    }

    response = await client.patch(f"/books/{old_book['id']}", json={})

    assert response.status_code == 401


    get_test_db_session.expire_all()
    existing_book = await get_test_db_session.get(Book, old_book['id'])

    assert existing_book.id == old_book['id']
    assert existing_book.author_id == old_book['author_id']
    assert existing_book.title == old_book['title']
    assert existing_book.pages == old_book['pages']


@pytest.mark.asyncio
async def test_patch_book_as_user_return_403(
        client: AsyncClient,
        fixed_books: list[Book],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    old_book = {
        "id": fixed_books[0].id,
        "author_id": fixed_books[0].author_id,
        "title": fixed_books[0].title,
        "pages": fixed_books[0].pages
    }

    response = await client.patch(f"/books/{old_book['id']}", json={})
    assert response.status_code == 403

    get_test_db_session.expire_all()
    existing_book = await get_test_db_session.get(Book, old_book['id'])

    assert existing_book.id == old_book['id']
    assert existing_book.author_id == old_book['author_id']
    assert existing_book.title == old_book['title']
    assert existing_book.pages == old_book['pages']


@pytest.mark.asyncio
async def test_patch_book_success_200(
client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
        fixed_books: list[Book]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)


    target_id = fixed_books[2].id
    new_author_id = fixed_books[0].author_id

    book_payload = {
        "title": "new_title_book",
        "pages": 1234,
        "author_id": new_author_id
    }

    response = await client.patch(f"/books/{target_id}", json=book_payload)

    response_validate = BookResponse.model_validate(response.json())

    assert book_payload['title'] == response_validate.title
    assert book_payload['pages'] == response_validate.pages
    assert book_payload['author_id'] == response_validate.author.id

    get_test_db_session.expire_all()

    query = select(Book).where(Book.id == target_id).options(selectinload(Book.author))
    result = await get_test_db_session.execute(query)
    db_book = result.scalar_one_or_none()
    assert db_book is not None

    db_book_validate = BookResponse.model_validate(db_book)

    assert db_book_validate == response_validate


@pytest.mark.parametrize(
    "exist_book_id, invalid_patch, expected_status, expected_error_loc, expected_error_type",
    (
        # Несуществующий id_book
        (False, {"title": "b1", "author_id": 999999, "pages": 12}, 404, "", ""),
        # Несуществующий автор
        (True, {"title": "b1", "author_id": 999999, "pages": 12}, 404, "", ""),
        # Отсутствует title (передана пустая строка)
        (True, {"title": "", "author_id": 1}, 422, "title", "string_too_short"),
        # Некорректный title >30
        (True, {"title": "b" * 40, "pages": 12}, 422, "title", "string_too_long"),
        # Некорректный тип у author_id
        (True, {"author_id": "", "pages": 12}, 422, "author_id", "int_parsing"),
        # Некорректный author_id < 0
        (True, {"title": "b4", "author_id": -1, "pages": 12}, 422, "author_id", "greater_than_equal"),
        # Некорректный pages < 1
        (True, {"title": "b5", "author_id": 1, "pages": -12}, 422, "pages", "greater_than_equal"),
    )
)
@pytest.mark.asyncio
async def test_patch_book_invalid_payloads_422_404(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
        fixed_books: list[Book],
        exist_book_id: bool,
        invalid_patch: dict[str, Any],
        expected_status: int,
        expected_error_loc: str,
        expected_error_type: str
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    if exist_book_id:
        target_id = fixed_books[0].id
    else:
        target_id = 99999

    response = await client.patch(f"/books/{target_id}", json=invalid_patch)
    assert response.status_code == expected_status
    if expected_status == 422:
        error_data = response.json()['detail'][0]
        assert expected_error_loc in error_data['loc'] and expected_error_type == error_data['type']


@pytest.mark.asyncio
async def test_delete_book_anonymous_return_401(
        client: AsyncClient,
        fixed_books: list[Book],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)
    response = await client.delete(f"/books/{fixed_books[0].id}")

    assert response.status_code == 401

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Book))
    existing_books = result.scalars().all()

    assert len(fixed_books) == len(existing_books)


@pytest.mark.asyncio
async def test_delete_book_as_user_return_403(
        client: AsyncClient,
        fixed_books: list[Book],
        get_test_db_session: AsyncSession,
        setup_auth
):

    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    response = await client.delete(f"/books/{fixed_books[0].id}")
    assert response.status_code == 403

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Book))
    existing_books = result.scalars().all()

    assert len(fixed_books) == len(existing_books)


@pytest.mark.asyncio
async def test_delete_book_success_204(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_books: list[Book]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    target = fixed_books[0]
    target_id = target.id

    response = await client.delete(f"/books/{target_id}")

    assert response.status_code == 204

    get_test_db_session.expire_all()

    author_db = await get_test_db_session.get(Book, target_id)


    assert author_db is None


@pytest.mark.asyncio
async def test_delete_book_not_found_404(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_books: list[Book]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    response = await client.delete("/books/999999")

    assert response.status_code == 404

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Book))
    existing_books = result.scalars().all()

    assert len(fixed_books) == len(existing_books)
