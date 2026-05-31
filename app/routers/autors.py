from typing import Optional, Any

from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import requre_roles, RoleChecker
from app.database import get_db_session
from app.models import Author
from app.schemas import AuthorInput, AuthorUpdate, AuthorResponse



router = APIRouter(prefix='/authors', tags=["Авторы"])
ITEMS_PER_PAGE = 10


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[AuthorResponse],
    summary="Получить список авторов с фильтрацией",
)
async def get_authors(
    author_name: Optional[str] = Query(None, description="Search by name"),
    country: Optional[str] = Query(None, description="Search by country"),
    db_session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1)
):
    """
    Возвращает список авторов с возможностью фильтрации.
    - **author_name**: Поиск по имени или фамилии автора (частичное совпадение)
    - **country**: Поиск по названию страны (без учёта регистра)
    """

    query = select(Author)
    if author_name:
        query = query.where(Author.full_name.ilike(f"%{author_name}%"))

    if country:
        query = query.where(Author.country.ilike(country))


    offset_value = (page - 1) * ITEMS_PER_PAGE
    query = query.offset(offset_value).limit(ITEMS_PER_PAGE)

    result = await db_session.execute(query)
    authors = result.scalars().all()
    return authors


@router.get(
    "/{author_id}",
    status_code=status.HTTP_200_OK,
    response_model=AuthorResponse,
    summary="Получить автора по ID",
    responses={
        404: {"description": "Автор с указанным ID не найден"},
    })
async def get_author_detail(author_id: int, db_session: AsyncSession = Depends(get_db_session)):
    """
    Возвращает подробную информацию об авторе по его уникальному ID.
    - **author_id**: ID автора
    """
    db_author = await db_session.get(
        Author,
        author_id
    )
    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found"
        )

    return db_author


@router.post(
"/",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthorResponse,
    summary="Создать нового автора",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"}
    }
)
async def create_author(
        author_data: AuthorInput,
        db_session: AsyncSession = Depends(get_db_session),
        payloads: dict[str, Any] = Depends(RoleChecker(["admin"]))):
    #payloads: dict[str, Any] = Depends(requre_roles(roles=["admin"]))
    """
    Создание нового автора. Требует аутентификации (Только администратор)
    Принимает JSON-объект с данными автора, валидирует их

    - **author_data**: Данные для создания автора

    Возвращает объект созданного автора с присвоенным ID из БД.
    """
    new_author = Author(**author_data.model_dump())
    db_session.add(new_author)
    await db_session.commit()
    await db_session.refresh(new_author)
    return new_author


@router.put(
    "/{author_id}",
    status_code=status.HTTP_200_OK,
    response_model=AuthorResponse,
    summary="Обновить/Заменить автора по ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Автор с указанным ID не найден"}
    }
)
async def put_author(
        author_id: int,
        author_data: AuthorInput,
        db_session: AsyncSession = Depends(get_db_session),
        payloads: dict[str, Any] = Depends(RoleChecker(["admin"]))):
    """
    Полное обновление (замена) данных автора. Требует аутентификации. (Только администратор)
    Принимает JSON-объект с данными книги, валидирует их

    - **author_id**: ID автора.
    - **author_data**: Новое полное состояние объекта (все обязательные поля должны быть переданы).

    Возвращает объект с заменёнными данными
    """
    db_author = await db_session.get(Author, author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author is not found"
        )

    update_data = author_data.model_dump()

    for key,val in update_data.items():
        setattr(db_author, key, val)

    await db_session.commit()

    return db_author


@router.patch(
    "/{author_id}",
    status_code=status.HTTP_200_OK,
    response_model=AuthorResponse,
    summary="Частично обновить объект по ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Автор с указанным ID не найден"}
    })
async def patch_author(
        author_id: int,
        author_data: AuthorUpdate,
        db_session: AsyncSession = Depends(get_db_session),
        payloads: dict[str, Any] = Depends(RoleChecker(["admin"]))
):
    """
    Частичное обновление данных автора. Требует аутентификации. (Только администратор)

    Принимает JSON-объект с данными автора, валидирует их.

    - **author_id**: ID автора
    - **author_data**: : Поля автора, которые необходимо изменить.

    Возвращает объект созданного автора
    """
    db_author = await db_session.get(Author, author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author is not found"
        )

    update_data = author_data.model_dump(exclude_unset=True)

    for key, val in update_data.items():
        setattr(db_author, key, val)

    return db_author


@router.delete(
    "/{author_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить автора по указанному ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Автор с указанным ID не найден"}
    }
)
async def delete_author(
        author_id: int,
        db_session: AsyncSession = Depends(get_db_session),
        payloads: dict[str, Any] = Depends(RoleChecker(["admin"]))
):
    """
    Удалить автора по указанному id. Требует аутентификации. (Только администратор)
    - **author_id**: ID удаляемого автора.
    """
    db_author = await db_session.get(Author, author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author is not found"
        )

    await db_session.delete(db_author)
    await db_session.commit()

    return None


