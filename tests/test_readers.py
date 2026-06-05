import pytest
from datetime import date
from typing import AsyncGenerator

from httpx import AsyncClient
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Reader, User, Book, Author, UserRole
from app.schemas import ReaderResponse


@pytest.fixture(scope="function")
async def clear_readers(
        get_test_db_session: AsyncSession
) -> AsyncGenerator[None, None]:
    yield
    await get_test_db_session.execute(delete(Author))
    await get_test_db_session.execute(delete(User))
    await get_test_db_session.commit()


@pytest.fixture(scope="function")
async def fixed_readers(
        get_test_db_session: AsyncSession,
        fixed_books: list[Book],
        clear_readers: None
) -> list[Reader]:
    usernames = ["username1", "username2", "username3"]
    users = []
    for username in usernames:
        user_reader = User(username=username, hashed_pass="12345678", role=UserRole.READER)
        get_test_db_session.add(user_reader)
        users.append(user_reader)

    await get_test_db_session.commit()

    for user in users:
        await get_test_db_session.refresh(user)

    readers = [
        Reader(
            full_name="reader1",
            books=[fixed_books[0]],
            register_date=date(1990,1,1),
            user_id=users[0].id,
            user=users[0]
        ),
        Reader(
            full_name="reader2",
            books=[fixed_books[0], fixed_books[1]],
            register_date=date(1995,1,1),
            user_id=users[1].id,
            user=users[1]
        ),
        Reader(
            full_name="reader3",
            books=[fixed_books[0], fixed_books[1], fixed_books[2]],
            register_date=date(1999,1,1),
            user_id=users[2].id,
            user=users[2]
        )
    ]

    get_test_db_session.add_all(readers)

    await get_test_db_session.commit()
    for reader in readers:
        await get_test_db_session.refresh(reader)

    query = select(Reader).where(Reader.id.in_([reader.id for reader in readers])).options(
        selectinload(Reader.books).selectinload(Book.author), selectinload(Reader.user))
    result = await get_test_db_session.execute(query)
    readers_with_relations = result.scalars().all()

    return list(readers_with_relations)


@pytest.mark.parametrize(
    "filter_params, expected_reader_names",
    [
        # без фильтров, ожидаем трёх
        ({},["reader1", "reader2","reader3"]),
        # фильтр по full_name - читателя, ожидаем r1
        ({"full_name": "reader1"}, ["reader1",]),
        # фильтр по book_title, ожидаем r2, r3
        ({"book_title": "b2"}, ["reader2", "reader3"]),
        # фильтр по book_title и full_name, ожидаем r2
        ({"book_title": "b2", "full_name": "reader2"}, ["reader2"]),
        # фильтр по start_date, ожидаем r2, r3
        ({"start_date": "1994-01-01"}, ["reader2", "reader3"]),
        # фильтр по end_date, ожидаем r1, r2
        ({"end_date": "1996-01-01"}, ["reader1", "reader2"]),
        # фильтр по start_date + end_date, ожидаем r2
        ({"start_date": "1994-01-01", "end_date": "1998-01-01"}, ["reader2"]),
        # фильтр по full_name, book_title, start_date + end_date, ожидаем r2
        (
            {"start_date": "1994-01-01",
             "end_date": "1998-01-01",
             "book_title": "b1",
             "full_name": "reader2"
             }, ["reader2"]
        ),
    ]
)
@pytest.mark.asyncio
async def test_get_readers_filtered_200(
        client: AsyncClient,
        fixed_readers: list[Reader],
        filter_params: dict[str],
        expected_reader_names: tuple[str, ...]
):


    response = await client.get("/readers/", params=filter_params)
    assert response.status_code == 200

    list_response_validate = [ReaderResponse.model_validate(res) for res in response.json()]
    print(list_response_validate)
    assert len(list_response_validate) == len(expected_reader_names)

    sorted_expected_usernames = sorted(expected_reader_names)
    sorted_response_usernames = sorted([r.full_name for r in list_response_validate])

    assert sorted_expected_usernames == sorted_response_usernames

    expected_readers_from_db = [r for r in fixed_readers if r.full_name in expected_reader_names]

    list_response_validate.sort(key= lambda r: r.full_name)
    expected_readers_from_db.sort(key=lambda r: r.full_name)

    assert len(list_response_validate) == len(expected_readers_from_db)


    for resp_reader, db_reader in zip(list_response_validate, expected_readers_from_db):
        assert resp_reader.id == db_reader.id
        assert resp_reader.full_name == db_reader.full_name
        assert resp_reader.user.username == db_reader.user.username
        assert resp_reader.user.id == db_reader.user.id
        assert resp_reader.register_date == db_reader.register_date
        resp_books_ids = sorted([r.id for r in resp_reader.books])
        db_books_ids = sorted([r.id for r in db_reader.books])
        assert resp_books_ids == db_books_ids


@pytest.mark.asyncio
async def test_get_reader_detail_200(
        client: AsyncClient,
        fixed_readers: list[Reader]
):
    target = fixed_readers[2]
    target_id = target.id
    response = await client.get(f"/readers/{target_id}")

    assert response.status_code == 200

    validate_response = ReaderResponse.model_validate(response.json())

    assert ReaderResponse.model_validate(target) == validate_response


@pytest.mark.asyncio
async def test_get_reader_detail_not_found_404(
        client: AsyncClient
):
    response = await client.get("/readers/9999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_put_reader_as_user_no_owner_403(
        client: AsyncClient,
        fixed_readers: list[Reader],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 99999, "role": "reader", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)

    old_data = {
        "id": fixed_readers[0].id,
        "user_id": fixed_readers[0].user_id,
        "full_name": fixed_readers[0].full_name,
        "register_date": fixed_readers[0].register_date,
        "books_ids": [b.id for b in fixed_readers[0].books]
    }
    response = await client.put(f"/readers/{old_data['id']}", json={})
    assert response.status_code == 403

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == old_data['id']).options(selectinload(Reader.books))
    result = await get_test_db_session.execute(query)
    existing_readers = result.scalar_one()

    assert existing_readers.id == old_data['id']
    assert existing_readers.user_id == old_data['user_id']
    assert existing_readers.full_name == old_data['full_name']
    assert existing_readers.register_date == old_data['register_date']

    sorted_books_ids_from_existing_readers = sorted([book.id for book in existing_readers.books])
    sorted_books_ids_from_old_data = sorted(old_data['books_ids'])
    assert sorted_books_ids_from_existing_readers == sorted_books_ids_from_old_data


@pytest.mark.asyncio
async def test_put_reader_as_anonymous_401(
        client: AsyncClient,
        fixed_readers: list[Reader],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 99999, "role": "reader", "exp": 123, "token_str": None}
    setup_auth(auth_behavior)

    old_data = {
        "id": fixed_readers[0].id,
        "user_id": fixed_readers[0].user_id,
        "full_name": fixed_readers[0].full_name,
        "register_date": fixed_readers[0].register_date,
        "books_ids": [b.id for b in fixed_readers[0].books]
    }
    response = await client.put(f"/readers/{old_data['id']}", json={})
    assert response.status_code == 401

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == old_data['id']).options(selectinload(Reader.books))
    result = await get_test_db_session.execute(query)
    existing_readers = result.scalar_one()

    assert existing_readers.id == old_data['id']
    assert existing_readers.user_id == old_data['user_id']
    assert existing_readers.full_name == old_data['full_name']
    assert existing_readers.register_date == old_data['register_date']

    sorted_books_ids_from_existing_readers = sorted([book.id for book in existing_readers.books])
    sorted_books_ids_from_old_data = sorted(old_data['books_ids'])
    assert sorted_books_ids_from_existing_readers == sorted_books_ids_from_old_data


@pytest.mark.asyncio
async def test_put_reader_success_200():
    pass


@pytest.mark.asyncio
async def test_put_reader_invalid_payloads_and_not_found_422_404():
    pass


@pytest.mark.asyncio
async def test_patch_reader_as_user_403():
    pass


@pytest.mark.asyncio
async def test_patch_reader_as_anonymous_401():
    pass


@pytest.mark.asyncio
async def test_patch_reader_success_200():
    pass


@pytest.mark.asyncio
async def test_patch_reader_invalid_payloads_and_not_found_422_404():
    pass



@pytest.mark.asyncio
async def test_add_book_to_reader_success_200():
    pass


@pytest.mark.asyncio
async def test_delete_book_from_reader_success_200():
    pass


@pytest.mark.asyncio
async def test_delete_reader_as_anonymous_401():
    pass


@pytest.mark.asyncio
async def test_delete_reader_success_200():
    pass


@pytest.mark.asyncio
async def test_delete_reader_success_200():
    pass



