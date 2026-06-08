from typing import Optional, Any

from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload, contains_eager
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import RoleChecker
from app.database import get_db_session
from app.models import Book, Author
from app.schemas import BookInput, BookUpdate, BookResponse

router = APIRouter(prefix="/books", tags=["Книги"])

ITEMS_PER_PAGE = 10


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[BookResponse],
    summary="Получить список книг с фильтрацией",
)
async def get_books(
    author_name: Optional[str] = Query(None, description="Search by author name"),
    book_title: Optional[str] = Query(None, description="Search by book title"),
    db_session: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
):
    """
    Возвращает список книг с возможностью фильтрации,
    подтягивает автора(one to many).

    - **author_name**: поиск по имени автора (частичное совпадение)
    - **book_title**: поиск по названию книги(частичное совпадение)
    """
    query = select(Book)
    if author_name:
        query = query.join(Book.author).where(
            Author.full_name.ilike(f"%{author_name}%")
        )
        query = query.options(contains_eager(Book.author))
    else:
        query = query.options(joinedload(Book.author))

    if book_title:
        query = query.where(Book.title.ilike(f"%{book_title}%"))

    offset_value = (page - 1) * ITEMS_PER_PAGE
    query = query.offset(offset_value).limit(ITEMS_PER_PAGE)

    result = await db_session.execute(query)
    return result.scalars().all()


@router.get(
    "/{book_id}",
    status_code=status.HTTP_200_OK,
    response_model=BookResponse,
    summary="Получить книгу по ID",
    responses={
        404: {"description": "Книга с указанным ID не найдена"},
    },
)
async def get_book_detail(
    book_id: int, db_session: AsyncSession = Depends(get_db_session)
):
    """
    Возвращает подробную информацию о книге по её уникальному ID,
    подтягивает автора(one to many) и список читателей (many-to-many связь)
    - **book_id**: ID книги
    """
    db_book = await db_session.get(Book, book_id, options=[joinedload(Book.author)])
    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book with this id is not found",
        )

    return db_book


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=BookResponse,
    summary="Создать новую книгу",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Автор с указанным ID не найден"},
    },
)
async def create_book(
    book_data: BookInput,
    db_session: AsyncSession = Depends(get_db_session),
    payloads: dict[str, Any] = Depends(RoleChecker(("admin",))),
):
    """
    Создание новой книги. Требует аутентификации (Только администратор).
    Принимает JSON-объект с данными книги, валидирует их,
    проверяет наличие указанного автора в БД,
    добавляет только существующих читателей

    - **book_data**: Данные для создания книги(схема BookInput)

    Возвращает объект созданной книги с присвоенным ID из БД,
    подтягивает автора(one to many) и список читателей (many-to-many связь)
    """
    db_author = await db_session.get(Author, book_data.author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found",
        )

    data_dict = book_data.model_dump()
    new_book = Book(**data_dict)

    # new_book.author = db_author
    db_session.add(new_book)

    await db_session.commit()
    await db_session.refresh(new_book)

    # get не подтягивает автора
    # book_with_relations = await db_session.get(Book, new_book.id, options=[joinedload(Book.author)])

    result = await db_session.execute(
        select(Book).where(Book.id == new_book.id).options(joinedload(Book.author))
    )

    book_with_relations = result.scalar_one()
    return book_with_relations


@router.put(
    "/{book_id}",
    status_code=status.HTTP_200_OK,
    response_model=BookResponse,
    summary="Обновить/Заменить книгу по ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Книга/Автор по указанному ID не найден."},
    },
)
async def put_book(
    book_id: int,
    book_data: BookInput,
    db_session: AsyncSession = Depends(get_db_session),
    payloads: dict[str, Any] = Depends(RoleChecker(("admin",))),
):
    """
    Полное обновление (замена) данных книги. Требует аутентификации (Только администратор).

    Принимает JSON-объект с данными книги, валидирует их,
    проверяет наличие указанного автора в бд,
    добавляет только существующих читателей.

    - **book_id**: ID книги.
    - **book_data**: Новое полное состояние объекта (все обязательные поля должны быть переданы).

    Возвращает объект с заменёнными данными, подтягивает автора(one to many) и список читателей (many-to-many связь)
    """
    db_book = await db_session.get(Book, book_id)

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Book is not found"
        )

    db_author = await db_session.get(Author, book_data.author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found",
        )

    update_data = book_data.model_dump()

    for key, val in update_data.items():
        setattr(db_book, key, val)

    await db_session.commit()

    result = await db_session.execute(
        select(Book).options(joinedload(Book.author)).where(Book.id == book_id)
    )

    book_with_relations = result.scalar_one()

    return book_with_relations


@router.patch(
    "/{book_id}",
    status_code=status.HTTP_200_OK,
    response_model=BookResponse,
    summary="Частично обновить книгу по ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Книга/Автор по указанному ID не найден."},
    },
)
async def patch_book(
    book_id: int,
    book_data: BookUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    payloads: dict[str, Any] = Depends(RoleChecker(("admin",))),
):
    """
    Частично обновить данные книги. Требует аутентификации (Только администратор)

    Принимает JSON-объект с данными книги, валидирует их,
    проверяет наличие автора в бд,
    проверяет наличие указанных читателей в БД,
    добавляет только существующих читателей.

    - **book_id**: ID книг
    - **book_data**: Поля книги, которые необходимо изменить.

    Возвращает книгу, подтягивает её автора(1tm) и читателей(mtm)
    """

    db_book = await db_session.get(Book, book_id)

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Book is not found"
        )

    if book_data.author_id:
        db_author = await db_session.get(Author, book_data.author_id)

        if db_author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author with this id is not found",
            )

    update_data = book_data.model_dump(exclude_unset=True)

    for key, val in update_data.items():
        setattr(db_book, key, val)

    await db_session.commit()

    result = await db_session.execute(
        select(Book).options(joinedload(Book.author)).where(Book.id == book_id)
    )

    book_with_relations = result.scalar_one()

    return book_with_relations


@router.delete(
    "/{book_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить книгу по указанному ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Недостаточно прав"},
        404: {"description": "Книга с указанным ID не найдена"},
    },
)
async def delete_book(
    book_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    payloads: dict[str, Any] = Depends(RoleChecker(("admin",))),
):
    """
    Удалить книгу по указанному id. Требует аутентификации (Только администратор).
    - **book_id**: ID удаляемой книги.
    """
    db_book = await db_session.get(Book, book_id)

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Book is not found"
        )

    await db_session.delete(db_book)
    await db_session.commit()

    return None
