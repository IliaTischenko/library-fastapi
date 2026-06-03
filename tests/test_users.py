import pytest
from typing import AsyncGenerator


from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession


from app.models import User, UserRole
from app.schemas import UserResponse


@pytest.fixture(scope="function")
async def clear_users(
        get_test_db_session: AsyncSession
) -> AsyncGenerator[None, None]:
    yield
    await get_test_db_session.execute(delete(User))
    await get_test_db_session.commit()


@pytest.fixture(scope="function")
async def create_users(
        get_test_db_session: AsyncSession,
        clear_users: AsyncGenerator[None, None]
) -> list[User]:
    users = [
        User(username="u1", hashed_pass="12345678", role=UserRole.ADMIN),
        User(username="u2", hashed_pass="12345678", role=UserRole.ADMIN),
        User(username="u3", hashed_pass="12345678", role=UserRole.ADMIN)
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
    auth_behavior = {"id": 1, "role": "reader", "exp": 123, "token": "at"}
    setup_auth(auth_behavior)

    response = await client.get("/users/")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_as_anonymous_401(
        client: AsyncClient,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token": None}
    setup_auth(auth_behavior)

    response = await client.get("/users/")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_users_success_200(
        client: AsyncClient,
        setup_auth,
        create_users: list[User]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token": "at"}
    setup_auth(auth_behavior)
    sorted_expected_usernames = ["u1", "u2", "u3"]

    response = await client.get("/users/")
    assert response.status_code == 200

    response_usernames = sorted([user['username'] for user in response.json()])

    assert response_usernames == sorted_expected_usernames



@pytest.mark.asyncio
async def test_register_admin_as_user_403(
        client: AsyncClient,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 123, "token": "at"}
    setup_auth(auth_behavior)

    response = await client.post("/users/register-admin", json={})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_admin_as_anonymous_401(
        client: AsyncClient,
        setup_auth,
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 123, "token": None}
    setup_auth(auth_behavior)

    response = await client.post("/users/register-admin", json={})

    assert response.status_code == 401



@pytest.mark.asyncio
async def test_register_admin_success_201(
        client: AsyncClient,
        setup_auth,
        clear_users,
        get_test_db_session: AsyncSession
):
    auth_behavior = {"id":1, "role": "admin", "exp": 123, "token": "at"}
    setup_auth(auth_behavior)

    admin_payload = {
        "username": "username_1",
        "password": "12345678"
    }

    response = await client.post("/users/register-admin", json=admin_payload)
    print(response.json())
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


#username занято
#username не указан + <5 >24
#password <8 >24 + пустой
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
    auth_behavior = {"id":1, "role": "admin", "exp": 123, "token": "at"}
    setup_auth(auth_behavior)


    response = await client.post("/users/register-admin", json=post_payload)

    print(response.json())
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
    auth_behavior = {"id":1, "role": "admin", "exp": 123, "token": "at"}
    setup_auth(auth_behavior)

    exists_admin = User(username="exists", hashed_pass="123456789", role=UserRole.ADMIN)
    get_test_db_session.add(exists_admin)
    await get_test_db_session.commit()

    new_admin_payload = {"username": exists_admin.username, "password":"12345678"}
    response = await client.post("/users/register-admin", json=new_admin_payload)

    assert response.status_code == 400