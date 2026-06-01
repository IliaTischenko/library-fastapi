from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from typing import AsyncGenerator, List, Callable, Any, NoReturn

from fastapi import HTTPException, status
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
async def create_authors(
        get_test_db_session: AsyncSession
) -> AsyncGenerator[List[Author], None]:
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
async def test_get_authors_filtered_200(
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
async def test_get_author_detail_200(
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
async def test_get_author_detail_not_found_404(
    client: AsyncClient,
    create_authors: list[Author]
):
    response = await client.get(f"/authors/312423431")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_author_anonymous_return_401(
        client: AsyncClient,
        setup_auth: Callable[[HTTPException | dict[str, Any]], dict[str, Any] | NoReturn]
):
    auth_behavior = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (Cookie missing/Token in blacklist)"
            )
    setup_auth(auth_behavior)
    response = await client.post("/authors/", data={})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_author_as_user_return_403(
        client: AsyncClient,
        setup_auth: Callable[[HTTPException | dict[str, Any]], dict[str, Any] | NoReturn]
):
    auth_behavior = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient rights"
    )

    setup_auth(auth_behavior)
    response = await client.post("/authors/", json={})
    data = response.json()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_author_success_201(
        client: AsyncClient,
        setup_auth: Callable[[HTTPException | dict[str, Any]], dict[str, Any] | NoReturn],
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

    #Проверяем базовый контракт: статус 201 и наличие сгенерированного ID
    assert response.status_code == 201

    validated_data = AuthorResponse.model_validate(response.json())

    #Проверяем что объект есть в бд
    result = await get_test_db_session.execute(select(Author).where(Author.id == validated_data.id))
    author_db = result.scalar_one_or_none()
    assert author_db is not None

    # Проверяем что объект такой же какой мы отправили
    expected_data = {
        "id": validated_data.id,
        "full_name": validated_data.full_name,
        "country": validated_data.country,
        "birth_date": validated_data.birth_date
    }

    assert validated_data.model_dump() == expected_data



@pytest.mark.parametrize(
    "invalid_payload, expected_errors_loc, expected_errors_type",
    [
        #1. Отсутствует full_name
        ({"full_name": "", "country": "RU", "birth_date": "1980-01-01"},
         ("full_name",),
         ("string_too_short",)
         ),
        #1. Отсутствует full_name и country
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
         )
    ]
)
@pytest.mark.asyncio
async def test_create_author_invalid_payloads_422(
        client: AsyncClient,
        setup_auth: Callable[[HTTPException | dict[str, Any]], dict[str, Any] | NoReturn],
        get_test_db_session: AsyncSession,
        clear_authors: None,
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
    # {'detail': [
    #     {'type': 'string_too_short', 'loc': ['body', 'full_name'], 'msg': 'String should have at least 1 character',
    #      'input': '', 'ctx': {'min_length': 1}}]}

    assert response.status_code == 422

    error_data = response.json()['detail']
    # error_data['detail'] == [{'type', 'loc'}, {}, {}]

    for i, loc_name in enumerate(expected_errors_loc):
        error_found = any(
               loc_name in err['loc'] and expected_errors_type[i] == err['type'] for err in error_data
        )

        print(error_data)
        assert error_found, f"Error not found for field {loc_name} with type {expected_errors_type[i]}"

