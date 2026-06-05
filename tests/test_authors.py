from datetime import date
import pytest
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator, List, Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author
from app.schemas import AuthorResponse


@pytest_asyncio.fixture(scope="function")
async def clear_authors(get_test_db_session: AsyncSession)  -> AsyncGenerator[None, None]:
    yield
    await get_test_db_session.execute(delete(Author))
    await get_test_db_session.commit()


@pytest_asyncio.fixture(scope="function")
async def fixed_authors(
        get_test_db_session: AsyncSession,
        clear_authors: None
) -> List[Author]:
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
async def test_get_authors_filtered_200(
        client: AsyncClient,
        filter_param: dict[str, str],
        expected_names: tuple[str],
        fixed_authors: list[Author]
):
    response = await client.get("/authors/", params=filter_param)
    assert response.status_code == 200

    list_validate_response = [AuthorResponse.model_validate(author) for author in response.json()]

    assert len(list_validate_response) == len(expected_names)

    sorted_response_names = sorted([author.full_name for author in list_validate_response])
    sorted_expected_names = sorted(
        author.full_name for author in fixed_authors if author.full_name in expected_names
    )

    assert sorted_response_names == sorted_expected_names

    expected_authors_from_db = [author for author in fixed_authors if author.full_name in expected_names]

    expected_authors_from_db.sort(key=lambda a: a.full_name)
    list_validate_response.sort(key=lambda a: a.full_name)

    for resp_author, db_author in zip(list_validate_response, expected_authors_from_db):
        assert resp_author.full_name == db_author.full_name
        assert resp_author.id == db_author.id
        assert resp_author.country == db_author.country
        assert resp_author.birth_date == db_author.birth_date


@pytest.mark.asyncio
async def test_get_author_detail_200(
    client: AsyncClient,
    fixed_authors: list[Author],
    get_test_db_session: AsyncSession
):
    target_author = fixed_authors[0]

    response = await client.get(f"/authors/{target_author.id}")
    assert response.status_code == 200

    validate_data = AuthorResponse.model_validate(response.json())

    assert AuthorResponse.model_validate(target_author) == validate_data


@pytest.mark.asyncio
async def test_get_author_detail_not_found_404(
    client: AsyncClient
):
    response = await client.get(f"/authors/312423431")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_create_author_anonymous_return_401(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.post("/authors/", data={})

    assert response.status_code == 401

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Author))
    existing_authors = result.scalars().all()

    assert len(existing_authors) == 0



@pytest.mark.asyncio
async def test_create_author_as_user_return_403(
        client: AsyncClient,
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)
    response = await client.post("/authors/", json={})
    assert response.status_code == 403

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Author))
    existing_authors = result.scalars().all()

    assert len(existing_authors) == 0


@pytest.mark.asyncio
async def test_create_author_success_201(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession,
        clear_authors: None
):
    auth_behavior = {
        "id": 1,
        "role": "admin",
        "exp": 1234,
        "token_str": "access_token"
    }
    setup_auth(auth_behavior)

    author_payloads = {
        "full_name": "a1",
        "country": "c1",
        "birth_date": "1978-05-10"
    }

    response = await client.post("/authors/", json=author_payloads)

    assert response.status_code == 201

    response_validated_data = AuthorResponse.model_validate(response.json())

    assert author_payloads['full_name'] == response_validated_data.full_name
    assert author_payloads['country'] == response_validated_data.country
    assert author_payloads['birth_date'] == str(response_validated_data.birth_date)

    get_test_db_session.expire_all()
    result = await get_test_db_session.execute(select(Author).where(Author.id == response_validated_data.id))
    author_db = result.scalar_one_or_none()
    assert author_db is not None

    author_db_validated = AuthorResponse.model_validate(author_db)

    assert response_validated_data == author_db_validated


@pytest.mark.parametrize(
    "invalid_payload, expected_errors_loc, expected_errors_type",
    [
        #1. Отсутствует full_name
        ({"full_name": "", "country": "RU", "birth_date": "1980-01-01"},
         ("full_name",),
         ("string_too_short",)
         ),
        #2. Отсутствует full_name и country
        ({"full_name": "", "country": "", "birth_date": "1980-01-01"},
         ("full_name", "country"),
         ("string_too_short", "string_too_short")
         ),
        #3.Отсутствует/Неверный формат даты
        ({"full_name": "Viktor Blood", "country": "RU", "birth_date": "ddddd"},
         ("birth_date",),
         ("date_from_datetime_parsing",)
         ),
        #4.Превышена допустимая длинна имени/страны
        ({
        "full_name": "Viktor Blood 123456789012345679",
        "country": "RU12345678901234561234567890123456797",
        "birth_date": "1980-01-01"
         },
         ("full_name", "country"),
         ("string_too_long", "string_too_long")
         ),
        #5.Отсутствует поле full_name
        ({"country": "RU", "birth_date": "1980-01-01"},
         ("full_name",),
         ("missing",)
         ),
        #6.Отсутствует поле country
        ({"full_name": "Viktor Blood", "birth_date": "1980-01-01"},
         ("country",),
         ("missing",)
         ),
        #6.Отсутствует birth_date
        ({"full_name": "Viktor Blood","country": "RU"},
         ("birth_date",),
         ("missing",)
         ),
    ]
)
@pytest.mark.asyncio
async def test_create_author_invalid_payloads_422(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession,
        invalid_payload: dict[str, Any],
        expected_errors_loc: list[str],
        expected_errors_type: list[str]

):
    auth_behavior = {
        "id": 1,
        "role": "admin",
        "exp": 1234,
        "token_str": "access_token"
    }
    setup_auth(auth_behavior)

    response = await client.post("/authors/", json=invalid_payload)

    assert response.status_code == 422

    error_data = response.json()['detail']
    for i, loc_name in enumerate(expected_errors_loc):
        error_found = any(
               loc_name in err['loc'] and expected_errors_type[i] == err['type'] for err in error_data
        )

        assert error_found, f"Error not found for field {loc_name} with type {expected_errors_type[i]}"




@pytest.mark.asyncio
async def test_put_author_anonymous_return_401(
        client: AsyncClient,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    old_data = {
        "id": fixed_authors[0].id,
        "full_name": fixed_authors[0].full_name,
        "country": fixed_authors[0].country,
        "birth_date": fixed_authors[0].birth_date
    }

    target_id = old_data["id"]

    response = await client.put(f"/authors/{target_id}", json={})

    assert response.status_code == 401

    get_test_db_session.expire_all()
    existing_author = await get_test_db_session.get(Author, target_id)

    assert old_data['full_name'] == existing_author.full_name
    assert old_data['country'] == existing_author.country
    assert old_data['birth_date'] == existing_author.birth_date


@pytest.mark.asyncio
async def test_put_author_as_user_return_403(
        client: AsyncClient,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)


    old_data = {
        "id": fixed_authors[0].id,
        "full_name": fixed_authors[0].full_name,
        "country": fixed_authors[0].country,
        "birth_date": fixed_authors[0].birth_date
    }

    target_id = old_data["id"]

    response = await client.put(f"/authors/{target_id}", json={})

    assert response.status_code == 403

    get_test_db_session.expire_all()
    existing_author = await get_test_db_session.get(Author, target_id)

    assert old_data['full_name'] == existing_author.full_name
    assert old_data['country'] == existing_author.country
    assert old_data['birth_date'] == existing_author.birth_date


@pytest.mark.parametrize(
    "use_valid_id, put_payload, expected_status, expected_errors_loc, expected_errors_type",
    [
        #1. Невалидный full_name <1
        (
            True,
            {"full_name": "", "country": "RU", "birth_date": "1980-01-01"},
            422,
            ("full_name",),
            ("string_too_short",)
         ),
        #2. Невалидный full_name и country
        (
            True,
            {"full_name": "", "country": "", "birth_date": "1980-01-01"},
            422,
            ("full_name", "country"),
            ("string_too_short", "string_too_short")
        ),
        #3.Автора нет в бд
        (
            False,
            {"full_name": "Viktor Blood", "country": "RU", "birth_date": "1980-01-01"},
            404,
            (),
            ()
         ),
        # 5.Отсутствует поле full_name
        (
            True,
            {"country": "RU", "birth_date": "1980-01-01"},
            422,
            ("full_name",),
            ("missing",)
        ),
        # 6.Отсутствует поле country
        (
            True,
            {"full_name": "Viktor Blood", "birth_date": "1980-01-01"},
            422,
            ("country",),
            ("missing",)
        ),
        # 6.Отсутствует birth_date
        (
            True,
            {"full_name": "Viktor Blood", "country": "RU"},
            422,
            ("birth_date",),
            ("missing",)
        ),
    ]
)
@pytest.mark.asyncio
async def test_put_author_invalid_payload_and_not_found_422_404(
        client: AsyncClient,
        setup_auth,
        get_test_db_session: AsyncSession,
        fixed_authors: list[Author],
        use_valid_id: bool,
        put_payload: dict[str, Any],
        expected_status: int,
        expected_errors_loc: list[str],
        expected_errors_type: list[str]

):
    auth_behavior = {
        "id": 1,
        "role": "admin",
        "exp": 1234,
        "token_str": "access_token"
    }
    setup_auth(auth_behavior)
    if use_valid_id:
        id_author = fixed_authors[0].id
    else:
        id_author = 99999

    response = await client.put(f"/authors/{id_author}", json=put_payload)

    assert response.status_code == expected_status

    if expected_status == 422:
        error_data = response.json()['detail']

        for i, loc_name in enumerate(expected_errors_loc):
            error_found = any(
                   loc_name in err['loc'] and expected_errors_type[i] == err['type'] for err in error_data
            )

            assert error_found, f"Error not found for field {loc_name} with type {expected_errors_type[i]}"


@pytest.mark.asyncio
async def test_put_author_success_201(
        client: AsyncClient,
        setup_auth,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
):
    auth_behavior = {"id": 2, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    target = fixed_authors[0]
    target_id = target.id

    new_payload = {
        "full_name": "new_name",
        "country": "new_country",
        "birth_date": "1900-01-02"
    }

    response = await client.put(f"/authors/{target_id}", json=new_payload)

    assert response.status_code == 200

    response_data = AuthorResponse.model_validate(response.json())
    assert response_data.full_name == new_payload['full_name']
    assert response_data.country == new_payload['country']
    assert response_data.birth_date.isoformat() == new_payload['birth_date']

    get_test_db_session.expire_all()

    author_db = await get_test_db_session.get(Author, target_id)
    assert author_db is not None
    assert author_db.full_name == response_data.full_name
    assert author_db.country == response_data.country
    assert author_db.birth_date == response_data.birth_date


@pytest.mark.asyncio
async def test_patch_author_anonymous_return_401(
        client: AsyncClient,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    old_data = {
        "id": fixed_authors[0].id,
        "full_name": fixed_authors[0].full_name,
        "country": fixed_authors[0].country,
        "birth_date": fixed_authors[0].birth_date
    }

    target_id = old_data["id"]

    response = await client.patch(f"/authors/{target_id}", json={})

    assert response.status_code == 401

    get_test_db_session.expire_all()
    existing_author = await get_test_db_session.get(Author, target_id)

    assert old_data['full_name'] == existing_author.full_name
    assert old_data['country'] == existing_author.country
    assert old_data['birth_date'] == existing_author.birth_date



@pytest.mark.asyncio
async def test_patch_author_as_user_return_403(
        client: AsyncClient,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    old_data = {
        "id": fixed_authors[0].id,
        "full_name": fixed_authors[0].full_name,
        "country": fixed_authors[0].country,
        "birth_date": fixed_authors[0].birth_date
    }

    target_id = old_data["id"]

    response = await client.patch(f"/authors/{target_id}", json={})
    assert response.status_code == 403

    get_test_db_session.expire_all()
    existing_author = await get_test_db_session.get(Author, target_id)

    assert old_data['full_name'] == existing_author.full_name
    assert old_data['country'] == existing_author.country
    assert old_data['birth_date'] == existing_author.birth_date


@pytest.mark.parametrize(
    "use_valid_id, patch_payload, expected_status, expected_err_loc, expected_err_type",
    [
        #Автора не существует
        (False,
        {"full_name": "Viktor Blood", "country": "RU", "birth_date": "1980-01-01"},
        404,
         (),
         ()
         ),
        #Автор существует ,поле full_name не валидно
        (
            True,
            {"full_name": ""}, #<1
            422,
            ("full_name",),
            ("string_too_short",)
        ),
        #Автор существует, поле full_name не валидно
        (
            True,
            {"full_name": "a" * 35},  # >30
            422,
            ("full_name",),
            ("string_too_long",)
        ),
        #Автор существует, изменённое поле не валидно
        (
            True,
            {"country": ""},  # <1
            422,
            ("country",),
            ("string_too_short",)
        ),
        #Автор существует, невалидный формат даты -> 422
        (
            True,
            {"birth_date": "not-a-date"},
            422,
            ("birth_date",),
            ("date_from_datetime_parsing",)
        )
    ]
)
@pytest.mark.asyncio
async def test_path_author_invalid_payload_and_not_found_422_404(
        client: AsyncClient,
        setup_auth,
        fixed_authors: list[Author],
        use_valid_id: bool,
        patch_payload: dict[str],
        expected_status: int,
        expected_err_loc: str,
        expected_err_type: str
):
    auth_behavior = {"id": 1, "role":"admin", "exp":123, "token_str": "access_token"}
    setup_auth(auth_behavior)

    if use_valid_id:
        target_id = fixed_authors[0].id
    else:
        target_id = 88888

    response = await client.patch(f"/authors/{target_id}", json=patch_payload)

    assert response.status_code == expected_status

    if use_valid_id:
        errors = response.json()['detail']
        for i, loc_name in enumerate(expected_err_loc):
            error_found = any(
                loc_name in err['loc'] and err['type'] == expected_err_type[i] for err in errors
            )
            assert error_found, f"Не найдена ошибка для поля '{loc_name}'"


@pytest.mark.parametrize(
    "patch_payload",
    [
        {"full_name": "new_name", "birth_date": "1900-01-02"},
        {"country": "new_country_1", "birth_date": "1922-01-02"},
        {"full_name": "new_name_1", "country": "new_country"}
    ]
)
@pytest.mark.asyncio
async def test_patch_author_success_201(
        client: AsyncClient,
        setup_auth,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        patch_payload: dict['str']
):
    auth_behavior = {"id": 2, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    target = fixed_authors[0]
    target_id = target.id


    response = await client.patch(f"/authors/{target_id}", json=patch_payload)

    assert response.status_code == 200

    response_data = AuthorResponse.model_validate(response.json())

    for key in patch_payload.keys():
        pydantic_val = getattr(response_data, key)
        if isinstance(pydantic_val, date):
            pydantic_val = pydantic_val.isoformat()

        assert pydantic_val == patch_payload[key],\
            f"Поле {key} не совпадает: Отправленное: {type(patch_payload[key])}, Ответ: {type(pydantic_val)}"

    get_test_db_session.expire_all()

    author_db = await get_test_db_session.get(Author, target_id)
    assert author_db is not None

    for field_name in AuthorResponse.model_fields.keys():
        db_val = getattr(author_db, field_name)
        pydantic_val = getattr(response_data, field_name)
        assert db_val == pydantic_val, f"Поле {field_name} не совпадает: БД: {db_val}, Ответ: {pydantic_val}"


@pytest.mark.asyncio
async def test_delete_author_anonymous_return_401(
        client: AsyncClient,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": None}
    setup_auth(auth_behavior)

    response = await client.delete(f"/authors/{fixed_authors[0].id}")

    assert response.status_code == 401

    result = await get_test_db_session.execute(select(Author))
    existing_authors = result.scalars().all()

    assert len(existing_authors) == len(fixed_authors)


@pytest.mark.asyncio
async def test_delete_author_as_user_return_403(
        client: AsyncClient,
        fixed_authors: list[Author],
        get_test_db_session: AsyncSession,
        setup_auth
):
    auth_behavior = {"id": 1, "role": "reader", "exp": 1, "token_str": "at"}
    setup_auth(auth_behavior)

    response = await client.delete(f"/authors/{fixed_authors[0].id}")
    assert response.status_code == 403

    result = await get_test_db_session.execute(select(Author))
    existing_authors = result.scalars().all()

    assert len(existing_authors) == len(fixed_authors)


@pytest.mark.asyncio
async def test_delete_author_success_204(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_authors: list[Author]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    target = fixed_authors[0]
    target_id = target.id

    response = await client.delete(f"/authors/{target_id}")
    assert response.status_code == 204

    get_test_db_session.expire_all()
    author_db = await get_test_db_session.get(Author, target_id)

    assert author_db is None


@pytest.mark.asyncio
async def test_delete_author_not_found_404(
    client: AsyncClient,
    setup_auth,
    get_test_db_session: AsyncSession,
    fixed_authors: list[Author]
):
    auth_behavior = {"id": 1, "role": "admin", "exp": 1, "token_str": "access_token"}
    setup_auth(auth_behavior)

    response = await client.delete("/authors/999999")

    assert response.status_code == 404

    result = await get_test_db_session.execute(select(Author))
    existing_authors = result.scalars().all()

    assert len(existing_authors) == len(fixed_authors)


