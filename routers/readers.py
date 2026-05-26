from datetime import date
from typing import Optional

from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload, contains_eager
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import get_current_id_admin_stateless
from database import get_db_session
from models import Reader, Book
from schemas import ReaderInput, ReaderUpdate, ReaderResponse


router = APIRouter(prefix='/readers', tags=["Читатели"])


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[ReaderResponse],
    summary="Получить список читателей с фильтрацией"
)
async def get_readers(
        name: Optional[str] = Query(None, description="Search by reader name"),
        book_title: Optional[str] = Query(None, description="Search reader with book title"),
        start_date: Optional[date] = Query(None, description="Search at date (to end_date)"),
        end_date: Optional[date] = Query(None, description="Search to date (at start_date)"),
        db_session: AsyncSession = Depends(get_db_session)
):
    """
    Получить список читателей с возможностью фильтациии, подтягивает список книг читателя(mtm связь)
    - **name**: поиск по имени читателя(частичное совпадение)
    - **book_title**: поиск по названию книги которую читатель брал(частичное совпадение)
    - **start_date**: поиск после указанной даты выдачи книг
    - **end_date** поиск до указанной даты выдачи книг
    в случае указания двух параметров start_date и end_date поиск осуществляется в диапазоне этих дат
    """

    query = select(Reader).options(selectinload(Reader.books).joinedload(Book.author))
    if name:
        query = query.where(Reader.full_name.ilike(f"%{name}%"))
    if book_title:
        query = (
            query.
            join(Reader.books).
            where(Book.title.ilike(f"%{book_title}%"))
        )
    if start_date:
        query = query.where(Reader.issue_date >= start_date)
    if end_date:
        query = query.where(Reader.issue_date <= end_date)



    result = await db_session.execute(query)
    readers = result.scalars().unique().all()

    return readers


@router.get(
    "/{reader_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReaderResponse,
    summary="Получить читателя по ID",
    responses={
        404: {"description": "Читатель с указанным ID не найден"}
    }
)
async def get_reader_detail(reader_id: int, db_session:AsyncSession = Depends(get_db_session)):
    """
    Возвращает подробную информацию о читателе по его уникальному ID, подтягивает список книг читателя(m2m связь)
    - **reader_id**: ID читателя
    """
    db_reader = await db_session.get(
        Reader,
        reader_id,
        options=[selectinload(Reader.books).joinedload(Book.author)]
    )
    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    return db_reader



@router.put(
    "/{reader_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReaderResponse,
    summary="Обновить/Заменить читателя по ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        404: {"description": "Читатель с указанным ID не найден"}
    })
async def put_reader(
        reader_id: int,
        reader_data: ReaderInput,
        db_session: AsyncSession = Depends(get_db_session),
        current_admin_id = Depends(get_current_id_admin_stateless)
):
    """
    Полное обновление (замена) данных читателя. Требует аутентификации

    Принимает JSON-объект с данными читателя, валидирует их,
    проверяет наличие указанных книг в БД,
    добавляет только существующие книги.

    - **reader_id**: ID читателя
    - **reader_data**: Новое полное состояние объекта (все обязательные поля должны быть переданы).

     Возвращает объект с заменёнными данными, подтягивает его книги(mtm связь) и их авторов(Book.author 1tm связь)
     """
    db_reader = await db_session.get(
        Reader,
        reader_id,
        options=[selectinload(Reader.books).joinedload(Book.author)])

    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    reader_dict = reader_data.model_dump()
    books_ids = reader_dict.pop("books_ids", [])
    if books_ids:
        result = await db_session.execute(
            select(Book).
            options(joinedload(Book.author)).
            where(Book.id.in_(books_ids))
        )
        books = result.scalars().all()
        db_reader.books = books


    for key, val in reader_dict.items():
        setattr(db_reader, key, val)

    await db_session.commit()

    result = await db_session.execute(
        select(Reader).
        options(selectinload(Reader.books).joinedload(Book.author)).
        where(Reader.id == reader_id)
    )
    reader_with_relations = result.scalar_one()

    return reader_with_relations


@router.patch(
    "/{reader_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReaderResponse,
    summary="Частично обновить читателя по ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        404: {"description": "Читатель с указанным ID не найден"}
    }
)
async def patch_reader(
        reader_id: int,
        reader_data: ReaderUpdate,
        db_session: AsyncSession = Depends(get_db_session),
        current_admin_id = Depends(get_current_id_admin_stateless)
):
    """
     Частично обновить данные читателя. Требует аутентификации.

     Принимает JSON-объект с данными читателя, валидирует их,
     проверяет наличие указанных книг в БД,
     добавляет только существующие книги.

    - **reader_id**: ID читателя
    - **reader_data**: Поля читателя, которые необходимо изменить.

     Возвращает читателя, подтягивает его книги(mtm) и их авторов(Book.author 1tm)
     """
    db_reader = await db_session.get(
        Reader,
        reader_id,
        options=[selectinload(Reader.books).joinedload(Book.author)])

    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    reader_dict = reader_data.model_dump(exclude_unset=True)
    books_ids = reader_dict.pop("books_ids", [])
    if books_ids:
        result = await db_session.execute(
            select(Book).
            options(joinedload(Book.author)).
            where(Book.id.in_(books_ids))
        )
        books = result.scalars().all()
        db_reader.books = books

    for key, val in reader_dict.items():
        setattr(db_reader, key, val)

    await db_session.commit()

    result = await db_session.execute(
        select(Reader).
        options(selectinload(Reader.books).joinedload(Book.author)).
        where(Reader.id == reader_id)
    )
    reader_with_relations = result.scalar_one()

    return reader_with_relations


@router.delete(
    "/{reader_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить читателя по указанному ID",
    responses={
        401: {"description": "Требуется аутентификация"},
        404: {"description": "Читатель с указанным ID не найден"}
        }
    )
async def delete_book(
        reader_id: int,
        db_session: AsyncSession = Depends(get_db_session),
        current_admin_id = Depends(get_current_id_admin_stateless)
):
    """
    Удалить читателя по указанному ID. Требует аутентификации.
    - **reader_id**: ID удаляемого читателя.
    """
    db_reader = await db_session.get(Reader, reader_id)
    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    await db_session.delete(db_reader)
    await db_session.commit()

    return None