from datetime import date
import pytest
from typing import AsyncGenerator, Any

from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import get_password_hash
from app.models import User, UserRole, Reader, Book
from app.schemas import UserResponse, ReaderResponse


@pytest.fixture(scope="function")
async def clear_users(
        get_test_db_session: AsyncSession
) -> AsyncGenerator[None, None]:
    yield
    await get_test_db_session.execute(delete(User))
    await get_test_db_session.commit()


@pytest.fixture(scope="function")
async def fixed_users(
        get_test_db_session: AsyncSession,
        clear_users: None
) -> list[User]:
    users = [
        User(username="username1", hashed_pass=get_password_hash("correct_password"), role=UserRole.ADMIN),
        User(username="username2", hashed_pass=get_password_hash("correct_password"), role=UserRole.ADMIN),
        User(username="username3", hashed_pass=get_password_hash("correct_password"), role=UserRole.ADMIN)
    ]

    for u in users:
        get_test_db_session.add(u)

    await get_test_db_session.commit()

    for u in users:
        await get_test_db_session.refresh(u)

    return users


@pytest.mark.asyncio
async def test_get_users_as_user_403(
        client: AsyncClient,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)

    response = await client.get("/users/")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_as_anonymous_401(
        client: AsyncClient,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.get("/users/")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_users_success_200(
        client: AsyncClient,
        setup_auth,
        fixed_users: list[User]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)
    expected_usernames = ["username1", "username2", "username3"]

    response = await client.get("/users/")
    assert response.status_code == 200

    list_response_validate = [UserResponse.model_validate(u) for u in response.json()]

    assert len(list_response_validate) == len(expected_usernames)

    sorted_expected_usernames = sorted(expected_usernames)
    sorted_response_usernames = sorted([u.username for u in list_response_validate])

    assert sorted_response_usernames == sorted_expected_usernames


    fixed_users.sort(key=lambda u: u.username)
    list_response_validate.sort(key=lambda u: u.username)

    for resp_user, db_user in zip(list_response_validate, fixed_users):
        assert resp_user.id == db_user.id
        assert resp_user.username == db_user.username
        assert resp_user.role == resp_user.role

@pytest.mark.asyncio
async def test_register_admin_as_user_403(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)

    response = await client.post("/users/register-admin", json={})
    assert response.status_code == 403

    result = await get_test_db_session.execute(select(User))
    existing_users = result.scalars().all()

    assert len(existing_users) == 0




@pytest.mark.asyncio
async def test_register_admin_as_anonymous_401(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.post("/users/register-admin", json={})

    assert response.status_code == 401

    result = await get_test_db_session.execute(select(User))
    existing_users = result.scalars().all()

    assert len(existing_users) == 0


@pytest.mark.asyncio
async def test_register_admin_success_201(
        client: AsyncClient,
        setup_auth,
        clear_users,
        get_test_db_session: AsyncSession
):
    auth_behavior = {"id":1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)

    admin_payload = {
        "username": "username_1",
        "password": "12345678"
    }

    response = await client.post("/users/register-admin", json=admin_payload)
    assert response.status_code == 201

    validate_response = UserResponse.model_validate(response.json())

    assert admin_payload['username'] == validate_response.username

    get_test_db_session.expire_all()

    admin_db = await get_test_db_session.get(User, validate_response.id)
    assert admin_db is not None

    admin_db_validate = UserResponse.model_validate(admin_db)

    assert validate_response.username == admin_db_validate.username
    assert validate_response.id == admin_db_validate.id
    assert validate_response.role == "admin"


@pytest.mark.parametrize(
    "post_payload, expected_err_loc, expecter_err_type",
    (
        #username пустой/<5
        ({"username": "", "password": "correct_pass"}, "username", "string_too_short"),
        #username >24
        ({"username": "g" * 25, "password": "correct_pass"}, "username", "string_too_long"),
        #password пустой/<8
        ({"username": "correct_username", "password": ""}, "password", "string_too_short"),
        #password >66
        ({"username": "correct_username", "password": "f" * 66}, "password", "string_too_long"),
        #Отсутствует поле username
        ({"password": "correct_pass"}, "username", "missing"),
        #Отсутствует поле password
        ({"username": "correct_username"}, "password", "missing"),
    )
)
@pytest.mark.asyncio
async def test_register_admin_invalid_payload_422(
        client: AsyncClient,
        setup_auth,
        clear_users,
        get_test_db_session: AsyncSession,
        post_payload: dict[str],
        expected_err_loc: str,
        expecter_err_type: str
):
    auth_behavior = {"id":1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)


    response = await client.post("/users/register-admin", json=post_payload)

    assert response.status_code == 422
    error = response.json()['detail'][0]
    assert expected_err_loc in error['loc'] and expecter_err_type == error['type']



@pytest.mark.asyncio
async def test_register_admin_already_exists_400(
        client: AsyncClient,
        setup_auth,
        clear_users,
        get_test_db_session: AsyncSession
):
    auth_behavior = {"id":1, "role": "admin", "exp": 123, "token_str": "at"}
    setup_auth(auth_behavior)

    exists_admin = User(username="exists", hashed_pass="123456789", role=UserRole.ADMIN)
    get_test_db_session.add(exists_admin)
    await get_test_db_session.commit()


    new_admin_payload = {"username": exists_admin.username, "password":"12345678"}
    response = await client.post("/users/register-admin", json=new_admin_payload)

    assert response.status_code == 400

    result = await get_test_db_session.execute(select(User))
    existing_users = result.scalars().all()

    assert len(existing_users) == 1


@pytest.mark.parametrize(
    "user_reader_payload, is_with_books",
    (
        #без книг и без даты
        ({
            "username": "user_1",
            "password": "password",
            "full_name": "Vitua Vityev",
            "books_ids": []
        }, False),
        #без книг, но с датой
        ({
            "username": "user_1",
            "password": "password",
            "full_name": "Vitua Vityev",
            "books_ids": [],
            "register_date": "1988-07-02"  # не обязательно
        }, False),
        #с книгами и с датой
        ({
            "username": "user_1",
            "password": "password",
            "full_name": "Vitua Vityev",
            "books_ids": [],
            "register_date": "1988-07-02"  # не обязательно
        }, True)
    )
)
@pytest.mark.asyncio
async def test_register_reader_success_201(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        clear_users: None,
        fixed_books: list[Book],
        user_reader_payload: dict[Any],
        is_with_books: bool
):

    if is_with_books:
        user_reader_payload['books_ids'] = [fixed_books[0].id, fixed_books[1].id, fixed_books[2].id]

    response = await client.post("/users/register-reader", json=user_reader_payload)

    assert response.status_code == 201

    validate_response = ReaderResponse.model_validate(response.json())

    sorted_books_id_payload = sorted(user_reader_payload['books_ids'])
    sorted_books_id_response = sorted([book.id for book in validate_response.books])
    if user_reader_payload.get('register_date', None):
        date_check = user_reader_payload['register_date']
    else:
        date_check = date.today().isoformat()


    assert user_reader_payload['username'] == validate_response.user.username
    assert user_reader_payload['full_name'] == validate_response.full_name
    assert sorted_books_id_payload == sorted_books_id_response
    assert date_check == validate_response.register_date.isoformat()

    get_test_db_session.expire_all()
    db_user = await get_test_db_session.get(User, validate_response.user.id)
    assert db_user is not None

    assert db_user.username == validate_response.user.username
    assert db_user.role == validate_response.user.role

    get_test_db_session.expire_all()
    query = (select(Reader).
             where(Reader.id == validate_response.id).
             options(selectinload(Reader.user),
                     selectinload(Reader.books)
                     )
             )
    result = await get_test_db_session.execute(query)
    db_reader = result.scalar_one_or_none()
    assert db_reader is not None


    sorted_books_id_form_db = sorted([book.id for book in db_reader.books])

    assert db_reader.full_name == validate_response.full_name
    assert sorted_books_id_form_db == sorted_books_id_payload
    assert db_reader.register_date.isoformat() == date_check


@pytest.mark.asyncio
async def test_patch_user_success_200(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_users: list[User],
        setup_auth
):
    target = fixed_users[0]
    target_id = target.id
    auth_behavior = {"id": target_id, "role": target.role, "exp": 123, "token_str": "ac"}
    setup_auth(auth_behavior)

    user_payload = {
        "old_password": "correct_password",
        "new_password": "new_password"
    }

    response = await client.patch("/users/", json=user_payload)
    assert response.status_code == 200


    validated_response = UserResponse.model_validate(response.json())

    assert target.id == validated_response.id
    assert target.username == validated_response.username

    get_test_db_session.expire_all()

    query = select(User).where(User.id == target_id)
    result = await get_test_db_session.execute(query)
    user_db = result.scalar_one_or_none()

    assert user_db is not None

    from app.auth_utils import verify_password as real_verify_password

    assert real_verify_password(user_payload["new_password"], user_db.hashed_pass) is True
    assert real_verify_password(user_payload["old_password"], user_db.hashed_pass) is False


@pytest.mark.parametrize(
    "is_user_exist, expected_status, patch_payload, expected_error_loc, expected_error_type",
    (
    #Юзера не существует
    (False, 404, {"old_password": "correct_password", "new_password": "new_correct_pass"}, "", ""),
    #Отсутствует поле old_password
    (True, 422, {"new_password": "new_correct_pass"}, "old_password", "missing"),
    #Отсутствует поле new_password
    (True, 422, {"old_password": "correct_password"}, "new_password", "missing"),
    # поле new_password невалидно < 8
    (True, 422, {"new_password": "", "old_password": "correct_password"}, "new_password", "string_too_short"),
    # поле new_password невалидно > 64
    (True, 422, {"new_password": "p" * 66, "old_password": "correct_password"}, "new_password", "string_too_long"),
    # поле old_password невалидно < 8
    (True, 422, {"new_password": "correct_password", "old_password": ""}, "old_password", "string_too_short"),
    # поле old_password невалидно > 64
    (True, 422, {"new_password": "correct_password", "old_password": "p" * 65}, "old_password", "string_too_long"),
    # поле new_password не совпадает со старым паролем
    (True, 400, {"new_password": "correct_password", "old_password": "corr_pass"}, "old_password", "string_too_long"),
    )
)
@pytest.mark.asyncio
async def test_patch_user_invalid_payload_422_404(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        fixed_users: list[User],
        setup_auth,
        is_user_exist: bool,
        expected_status: int,
        patch_payload: dict[str],
        expected_error_loc: str,
        expected_error_type: str
):
    if not is_user_exist:
        auth_behavior = {"id": 9999999, "role": "admin", "exp": 123, "token_str": "ac"}
    else:
        target = fixed_users[0]
        target_id = target.id
        auth_behavior = {"id": target_id, "role": "admin", "exp": 123, "token_str": "ac"}

    setup_auth(auth_behavior)

    response = await client.patch("/users/", json=patch_payload)

    assert response.status_code == expected_status

    if expected_status == 422:
        error = response.json()['detail'][0]
        assert expected_error_loc in error['loc'] and expected_error_type == error['type']


@pytest.mark.asyncio
async def test_delete_user_anonymous_return_401(
        client: AsyncClient,
        fixed_users: list[User],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)
    response = await client.delete(f"/users/{fixed_users[0].id}")

    assert response.status_code == 401

    result = await get_test_db_session.execute(select(User))
    existing_users = result.scalars().all()

    assert len(existing_users) == len(fixed_users)


@pytest.mark.asyncio
async def test_delete_user_as_user_return_403(
        client: AsyncClient,
        fixed_users: list[User],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)
    response = await client.delete(f"/users/{fixed_users[0].id}")
    assert response.status_code == 403

    result = await get_test_db_session.execute(select(User))
    existing_users = result.scalars().all()

    assert len(existing_users) == len(fixed_users)


@pytest.mark.asyncio
async def test_delete_user_success_204(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_users: list[User]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    target = fixed_users[0]
    target_id = target.id

    response = await client.delete(f"/users/{target_id}")

    assert response.status_code == 204

    get_test_db_session.expire_all()

    user_db = await get_test_db_session.get(User, target_id)
    assert user_db is None


@pytest.mark.asyncio
async def test_delete_user_not_found_404(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_users: list[User]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    response = await client.delete("/users/999999")

    assert response.status_code == 404

    result = await get_test_db_session.execute(select(User))
    existing_users = result.scalars().all()

    assert len(existing_users) == len(fixed_users)
