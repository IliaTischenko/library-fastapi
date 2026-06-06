from http.client import responses

import pytest
from datetime import date
from typing import AsyncGenerator, Any

from httpx import AsyncClient
from sqlalchemy import select, delete, True_
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
    auth_behavior = {"id": 99999, "role": "admin", "exp": 123, "token_str": None}
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


@pytest.mark.parametrize(
    "put_payload_pre",
    [
        ({
            "full_name": "new_reader_name",
            "books_indices": [0, 1],
            "register_date": "1888-10-03"
        }
        ),
        ({
            "full_name": "new_reader_name",
            "books_indices": [],
            "register_date": "1888-10-03"
        }),
        ({
            "full_name": "new_reader_name",
            "books_indices": []
        })
    ]
)
@pytest.mark.asyncio
async def test_put_reader_success_200(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth,
        put_payload_pre: dict[str, Any]
):
    target = fixed_readers[0]
    target_id = target.id

    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)

    real_books_ids = [fixed_books[idx].id for idx in put_payload_pre['books_indices']]

    put_payload = {
        "full_name": put_payload_pre['full_name'],
        "books_ids": real_books_ids
    }
    if put_payload_pre.get("register_date"):
        put_payload['register_date'] = put_payload_pre['register_date']

    response = await client.put(f"/readers/{target_id}", json=put_payload)
    print(response.json())
    assert response.status_code == 200


    response_validate = ReaderResponse.model_validate(response.json())

    actual_data = response_validate.model_dump(include={"full_name", "register_date"}, mode="json")
    actual_books_ids = [b.id for b in response_validate.books]

    assert actual_data['full_name'] == put_payload['full_name']
    if put_payload_pre.get('register_date'):
        assert actual_data['register_date'] == put_payload['register_date']
    assert sorted(actual_books_ids) == sorted(put_payload['books_ids'])

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == target_id).options(
        selectinload(Reader.books).selectinload(Book.author),
        selectinload(Reader.user)
    )
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one_or_none()
    assert db_reader is not None

    validate_db_reader = ReaderResponse.model_validate(db_reader)

    assert validate_db_reader == response_validate


@pytest.mark.parametrize(
    "invalid_payload, expected_status, expected_err_loc, expected_err_type",
    [
        #full_name <1
        ({"full_name": "",
        "books_ids": [1, 2],
        "register_date": "1888-10-03"}, 422, "full_name", "string_too_short"),
        # full_name >30
        ({"full_name": "a" * 31,
          "books_ids": [1, 2],
          "register_date": "1888-10-03"}, 422, "full_name", "string_too_long"),
        # full_name отсутствует
        ({"books_ids": [1, 2],
          "register_date": "1888-10-03"}, 422, "full_name", "missing"),
        # books_ids < 0
        ({"full_name": "correct_name",
          "books_ids": [-1, 2],
          "register_date": "1888-10-03"}, 422, "books_ids", "greater_than_equal"),
        # books_ids отсутствует
        ({"full_name": "correct_name",
          "register_date": "1888-10-03"}, 422, "books_ids", "missing"),
        # books_ids некорректны
        ({"full_name": "correct_name",
          "books_ids": ["1", "2"],
          "register_date": "1888-10-03"}, 422, "books_ids", "int_type"),
        # register_date некоректна
        ({"full_name": "correct_name",
          "books_ids": [1, 2],
          "register_date": "1998-33-33"}, 422, "register_date", "date_from_datetime_parsing"),
        # register_date пустая
        ({"full_name": "correct_name",
          "books_ids": [1, 2],
          "register_date": ""}, 422, "register_date", "date_from_datetime_parsing"),
        #reader_id не сущетсвует
        ({
            "full_name": "new_reader_name",
            "books_ids": [1, 2],
            "register_date": "1888-10-03"
        }, 404, "", "")

    ]
)
@pytest.mark.asyncio
async def test_put_reader_invalid_payloads_and_not_found_422_404(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        setup_auth,
        invalid_payload: dict[str, Any],
        expected_status: int,
        expected_err_loc: str,
        expected_err_type: str
):
    target = fixed_readers[0]
    if expected_status == 404:
        target_id = 99999
    else:
        target_id = target.id

    old_data = {
        "id": target.id,
        "user_id": target.user_id,
        "user": target.user,
        "full_name": target.full_name,
        "register_date": target.register_date,
        "books": target.books
    }

    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)


    response = await client.put(f"/readers/{target_id}", json=invalid_payload)
    assert response.status_code == expected_status

    print(response.json())
    if response.status_code == 422:
        error = response.json()['detail'][0]

        assert expected_err_loc in error['loc'] and expected_err_type == error['type']


        get_test_db_session.expire_all()
        query = select(Reader).where(Reader.id == target_id).options(
            selectinload(Reader.books).selectinload(Book.author),
            selectinload(Reader.user)
        )
        result = await get_test_db_session.execute(query)
        db_reader = result.scalar_one_or_none()
        assert db_reader is not None

        validate_db_reader = ReaderResponse.model_validate(db_reader)
        validate_old_data = ReaderResponse.model_validate(old_data)

        assert validate_db_reader == validate_old_data


@pytest.mark.asyncio
async def test_patch_reader_as_user_no_owner_403(
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
    response = await client.patch(f"/readers/{old_data['id']}", json={})
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
async def test_patch_reader_as_anonymous_401(
    client: AsyncClient,
    fixed_readers: list[Reader],
    get_test_db_session: AsyncSession,
    setup_auth
):
    auth_behavior = {"id": 99999, "role": "admin", "exp": 123, "token_str": None}
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


@pytest.mark.parametrize(
    "patch_payload_pre",
    [
        ({
            "full_name": "correct_name",
            "books_indices": [1, 2],
            "register_date": "1987-02-05"
        }),
        ({
             #full_name - отсутствует
             "books_indices": [1, 2],
             "register_date": "1987-02-05"
        }),
        ({
             #books_ids - отсутствует
             "full_name": "correct_name",
             "register_date": "1987-02-05"
        }),
        ({# register_date - отсутствует
             "full_name": "correct_name",
              "books_indices": [1, 2],
        }),
    ]
)
@pytest.mark.asyncio
async def test_patch_reader_success_200(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        patch_payload_pre: dict[str, Any]
):
    target = fixed_readers[0]
    target_id = target.id

    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": "ac"}
    setup_auth(auth_behavior)

    patch_payload = {}
    real_books_ids = []
    for key in patch_payload_pre.keys():
        if key == "books_indices":
            real_books_ids = sorted([int(fixed_books[int(idx)].id) for idx in patch_payload_pre["books_indices"]])
            patch_payload['books_ids'] = real_books_ids
        patch_payload[key] =  patch_payload_pre[key]

    response = await client.patch(f"/readers/{target_id}", json=patch_payload)
    assert response.status_code == 200

    validate_response = ReaderResponse.model_validate(response.json())

    if patch_payload.get("full_name"):
        assert patch_payload.get("full_name") == validate_response.full_name
    if patch_payload.get("register_date"):
        assert patch_payload.get("register_date") == validate_response.register_date.isoformat()
    if patch_payload.get("books_ids"):
        assert real_books_ids == sorted([b.id for b in validate_response.books])


    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == target_id).options(
        selectinload(Reader.books).selectinload(Book.author),
        selectinload(Reader.user)
    )
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one_or_none()

    assert db_reader is not None

    validate_db_reader = ReaderResponse.model_validate(db_reader)

    assert validate_db_reader == validate_response


@pytest.mark.parametrize(
    "invalid_payload, expected_status, expected_err_loc, expected_err_type",
    [
        #full_name <1
        ({"full_name": "",
        "books_ids": [1, 2],
        "register_date": "1888-10-03"}, 422, "full_name", "string_too_short"),
        # full_name >30
        ({"full_name": "a" * 31,
          "books_ids": [1, 2],
          "register_date": "1888-10-03"}, 422, "full_name", "string_too_long"),
        # books_ids < 0
        ({"full_name": "correct_name",
          "books_ids": [-1, 2],
          "register_date": "1888-10-03"}, 422, "books_ids", "greater_than_equal"),
        # books_ids некорректны
        ({"full_name": "correct_name",
          "books_ids": ["1", "2"],
          "register_date": "1888-10-03"}, 422, "books_ids", "int_type"),
        # register_date некоректна
        ({"full_name": "correct_name",
          "books_ids": [1, 2],
          "register_date": "1998-33-33"}, 422, "register_date", "date_from_datetime_parsing"),
        # register_date пустая
        ({"full_name": "correct_name",
          "books_ids": [1, 2],
          "register_date": ""}, 422, "register_date", "date_from_datetime_parsing"),
        #reader_id не сущетсвует
        ({
            "full_name": "new_reader_name",
            "books_ids": [1, 2],
            "register_date": "1888-10-03"
        }, 404, "", "")

    ]
)
@pytest.mark.asyncio
async def test_patch_reader_invalid_payloads_and_not_found_422_404(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        setup_auth,
        invalid_payload: dict[str, Any],
        expected_status: int,
        expected_err_loc: str,
        expected_err_type: str
):
    target = fixed_readers[0]
    if expected_status == 404:
        target_id = 99999
    else:
        target_id = target.id

    old_data = {
        "id": target.id,
        "user_id": target.user_id,
        "user": target.user,
        "full_name": target.full_name,
        "register_date": target.register_date,
        "books": target.books
    }

    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)


    response = await client.patch(f"/readers/{target_id}", json=invalid_payload)
    assert response.status_code == expected_status

    print(response.json())
    if response.status_code == 422:
        error = response.json()['detail'][0]

        assert expected_err_loc in error['loc'] and expected_err_type == error['type']


        get_test_db_session.expire_all()
        query = select(Reader).where(Reader.id == target_id).options(
            selectinload(Reader.books).selectinload(Book.author),
            selectinload(Reader.user)
        )
        result = await get_test_db_session.execute(query)
        db_reader = result.scalar_one_or_none()
        assert db_reader is not None

        validate_db_reader = ReaderResponse.model_validate(db_reader)
        validate_old_data = ReaderResponse.model_validate(old_data)

        assert validate_db_reader == validate_old_data


@pytest.mark.asyncio
async def test_add_book_to_reader_success_200(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "ac"}
    setup_auth(auth_behavior)

    target_reader = fixed_readers[0] #books 0,1
    target_reader_id = target_reader.id
    target_reader_books_ids = [b.id for b in target_reader.books]

    target_book_id = fixed_books[2].id

    expected_books_ids = target_reader_books_ids
    expected_books_ids.append(target_book_id)

    sorted_expected_books_ids = sorted(expected_books_ids)

    response = await client.post(f"/readers/{target_reader_id}/books/{target_book_id}")
    assert response.status_code == 200

    validated_response = ReaderResponse.model_validate(response.json())

    sorted_validated_response_books_ids = sorted(b.id for b in validated_response.books)

    assert sorted_expected_books_ids == sorted_validated_response_books_ids

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one_or_none()
    assert db_reader is not None

    sorted_db_reader_books_ids = sorted([b.id for b in db_reader.books])
    assert sorted_validated_response_books_ids == sorted_db_reader_books_ids


@pytest.mark.parametrize(
    "is_reader_exist, is_owner, is_book_exist, is_book_already_added , expected_status",
    [
        (False, True, True, False, 404),
        (True, False, True, False, 403),
        (True, True, False, False, 404),
        (True, True, True, True, 400)
    ]
)
@pytest.mark.asyncio
async def test_add_book_to_reader_invalid_payload_404_403_400(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth,
        is_reader_exist: bool,
        is_owner: bool,
        is_book_exist: bool,
        is_book_already_added: bool,
        expected_status: int
):
    if not is_owner:
        user_id = fixed_readers[1].user_id
        role = "reader"
    else:
        user_id = 1
        role = "admin"

    auth_behavior = {"id": user_id, "role": role, "exp": 1, "token_str": "ac"}
    setup_auth(auth_behavior)

    target = fixed_readers[0]
    target_reader_id = target.id

    if not is_reader_exist:
        target_reader_id = 99999

    target_book_id = fixed_books[2].id
    if not is_book_exist:
        target_book_id = 99999

    if is_book_already_added:
        target_book_id = fixed_books[0].id

    expected_books_ids = [b.id for b in target.books]

    sorted_expected_books_ids = sorted(expected_books_ids)

    response = await client.post(f"/readers/{target_reader_id}/books/{target_book_id}")

    assert response.status_code == expected_status

    if is_reader_exist:
        get_test_db_session.expire_all()
        query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
        result = await get_test_db_session.execute(query)
        db_reader = result.scalar_one_or_none()

        assert db_reader is not None

        db_book_ids = sorted([b.id for b in db_reader.books])

        assert db_book_ids == sorted_expected_books_ids


@pytest.mark.asyncio
async def test_add_book_to_reader_as_user_no_owner_403(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth
):
    target = fixed_readers[0]
    target_reader_id = target.id
    target_book_id = fixed_books[2].id
    sorted_expected_books_ids = sorted([b.id for b in target.books])

    auth_behavior = {"id": fixed_readers[1].user_id, "role": "reader", "exp": 123, "token_str": "ac"}
    setup_auth(auth_behavior)

    response = await client.post(f"/readers/{target_reader_id}/books/{target_book_id}")
    assert response.status_code == 403

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one()

    sorted_db_books_ids = sorted([b.id for b in db_reader.books])

    assert sorted_expected_books_ids == sorted_db_books_ids


@pytest.mark.asyncio
async def test_add_book_to_reader_as_anonymous_401(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth
):
    target = fixed_readers[0]
    target_reader_id = target.id
    target_book_id = fixed_books[2].id
    sorted_expected_books_ids = sorted([b.id for b in target.books])

    auth_behavior = {"id": 1, "role": "reader", "exp": 123, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.post(f"/readers/{target_reader_id}/books/{target_book_id}")
    assert response.status_code == 401

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one()

    sorted_db_books_ids = sorted([b.id for b in db_reader.books])

    assert sorted_expected_books_ids == sorted_db_books_ids


@pytest.mark.asyncio
async def test_delete_book_from_reader_success_200(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "ac"}
    setup_auth(auth_behavior)

    target_reader = fixed_readers[0] #books 0,1
    target_reader_id = target_reader.id
    target_reader_books_ids = [b.id for b in target_reader.books]

    target_book_id = target_reader.books[0].id #0

    expected_books_ids = target_reader_books_ids
    expected_books_ids.remove(target_book_id)

    sorted_expected_books_ids = sorted(expected_books_ids)

    response = await client.delete(f"/readers/{target_reader_id}/books/{target_book_id}")

    assert response.status_code == 200

    validated_response = ReaderResponse.model_validate(response.json())

    sorted_validated_response_books_ids = sorted(b.id for b in validated_response.books)

    assert sorted_expected_books_ids == sorted_validated_response_books_ids

    get_test_db_session.expire_all()
    query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one_or_none()
    assert db_reader is not None

    sorted_db_reader_books_ids = sorted([b.id for b in db_reader.books])
    assert sorted_validated_response_books_ids == sorted_db_reader_books_ids


@pytest.mark.parametrize(
    "is_reader_exist, is_owner, is_book_exist, is_book_already_deleted , expected_status",
    [
        (False, True, True, False, 404),
        (True, False, True, False, 403),
        (True, True, False, False, 400),
        (True, True, True, True, 400)
    ]
)
@pytest.mark.asyncio
async def test_delete_book_from_reader_invalid_payload_404_403_400(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth,
        is_reader_exist: bool,
        is_owner: bool,
        is_book_exist: bool,
        is_book_already_deleted: bool,
        expected_status: int
):
    if not is_owner:
        user_id = fixed_readers[2].user_id
        role = "reader"
    else:
        user_id = 1
        role = "admin"

    auth_behavior = {"id": user_id, "role": role, "exp": 1, "token_str": "ac"}
    setup_auth(auth_behavior)

    target = fixed_readers[1]
    target_reader_id = target.id

    if not is_reader_exist:
        target_reader_id = 99999

    target_book_id = fixed_books[0].id
    if not is_book_exist:
        target_book_id = 99999

    if is_book_already_deleted:
        target_book_id = fixed_books[2].id

    expected_books_ids = [b.id for b in target.books]

    sorted_expected_books_ids = sorted(expected_books_ids)

    response = await client.delete(f"/readers/{target_reader_id}/books/{target_book_id}")

    assert response.status_code == expected_status

    if is_reader_exist:
        get_test_db_session.expire_all()
        query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
        result = await get_test_db_session.execute(query)
        db_reader = result.scalar_one_or_none()

        assert db_reader is not None

        db_book_ids = sorted([b.id for b in db_reader.books])

        assert db_book_ids == sorted_expected_books_ids


@pytest.mark.asyncio
async def test_delete_book_form_reader_as_user_no_owner_403(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth
    ):
        target = fixed_readers[2]
        target_reader_id = target.id
        target_book_id = fixed_books[2].id
        sorted_expected_books_ids = sorted([b.id for b in target.books])

        auth_behavior = {"id": fixed_readers[1].user_id, "role": "reader", "exp": 123, "token_str": "ac"}
        setup_auth(auth_behavior)

        response = await client.delete(f"/readers/{target_reader_id}/books/{target_book_id}")
        assert response.status_code == 403

        get_test_db_session.expire_all()
        query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
        result = await get_test_db_session.execute(query)
        db_reader = result.scalar_one()

        sorted_db_books_ids = sorted([b.id for b in db_reader.books])

        assert sorted_expected_books_ids == sorted_db_books_ids


@pytest.mark.asyncio
async def test_delete_book_from_reader_as_anonymous_401(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_readers: list[Reader],
        fixed_books: list[Book],
        setup_auth
    ):
        target = fixed_readers[2]
        target_reader_id = target.id
        target_book_id = fixed_books[2].id
        sorted_expected_books_ids = sorted([b.id for b in target.books])

        auth_behavior = {"id": fixed_readers[1].user_id, "role": "admin", "exp": 123, "token_str": None}
        setup_auth(auth_behavior)

        response = await client.delete(f"/readers/{target_reader_id}/books/{target_book_id}")
        assert response.status_code == 401

        get_test_db_session.expire_all()
        query = select(Reader).where(Reader.id == target_reader_id).options(selectinload(Reader.books))
        result = await get_test_db_session.execute(query)
        db_reader = result.scalar_one()

        sorted_db_books_ids = sorted([b.id for b in db_reader.books])

        assert sorted_expected_books_ids == sorted_db_books_ids


@pytest.mark.asyncio
async def test_delete_author_anonymous_return_401(
        client: AsyncClient,
        fixed_readers: list[Reader],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.delete(f"/readers/{fixed_readers[0].id}")

    assert response.status_code == 401

    result = await get_test_db_session.execute(select(Reader))
    db_readers = result.scalars().all()

    assert len(db_readers) == len(fixed_readers)


@pytest.mark.asyncio
async def test_delete_reader_as_user_403(
        client: AsyncClient,
        fixed_readers: list[Reader],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    response = await client.delete(f"/readers/{fixed_readers[0].id}")
    assert response.status_code == 403

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Reader))
    db_readers = result.scalars().all()

    assert len(db_readers) == len(fixed_readers)


@pytest.mark.asyncio
async def test_delete_reader_success_204(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_readers: list[Author]

):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    target = fixed_readers[0]
    target_id = target.id

    response = await client.delete(f"/readers/{target_id}")
    assert response.status_code == 204

    get_test_db_session.expire_all()
    reader_db = await get_test_db_session.get(Reader, target_id)

    assert reader_db is None


@pytest.mark.asyncio
async def test_delete_reader_not_found_404(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_readers: list[Reader]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    response = await client.delete("/readers/999999")

    assert response.status_code == 404

    result = await get_test_db_session.execute(select(Reader))
    existing_authors = result.scalars().all()

    assert len(existing_authors) == len(fixed_readers)




