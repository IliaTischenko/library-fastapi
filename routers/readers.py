from datetime import date
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, contains_eager

from database import get_db_session
from schemas import ReaderInput, ReaderUpdate, ReaderResponse
from sqlalchemy import select
from models import Reader, Book


router = APIRouter(prefix='/readers', tags=["Readers"])


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[ReaderResponse])
async def get_readers(
        name: Optional[str] = Query(None, description="Search by reader name"),
        book_title: Optional[str] = Query(None, description="Search reader with book title"),
        start_date: Optional[date] = Query(None, description="Search at date (to end_date)"),
        end_date: Optional[date] = Query(None, description="Search to date (at start_date)"),
        db_session: AsyncSession = Depends(get_db_session)
):

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


@router.get("/{reader_id}", status_code=status.HTTP_200_OK, response_model=ReaderResponse)
async def get_reader_detail(reader_id: int, db_session:AsyncSession = Depends(get_db_session)):
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

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ReaderResponse)
async def create_reader(reader_data: ReaderInput, db_session: AsyncSession = Depends(get_db_session)):
    data_dict = reader_data.model_dump()
    books_ids = data_dict.pop("books_ids", [])
    new_reader = Reader(**data_dict)

    if books_ids:
        query = select(Book).where(Book.id.in_(books_ids))
        result = await db_session.execute(query)
        books = result.scalars().all()
        new_reader.books = books

    db_session.add(new_reader)
    await db_session.commit()
    await db_session.refresh(new_reader)

    result = await db_session.execute(
        select(Reader)
        .options(selectinload(Reader.books).joinedload(Book.author))
        .where(Reader.id == new_reader.id)
    )
    reader_with_relations = result.scalar_one()

    return reader_with_relations


@router.put("/{reader_id}", status_code=status.HTTP_200_OK, response_model=ReaderResponse)
async def put_reader(reader_id: int, reader_data: ReaderInput, db_session: AsyncSession = Depends(get_db_session)):
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


@router.patch("/{reader_id}", status_code=status.HTTP_200_OK, response_model=ReaderResponse)
async def put_reader(reader_id: int, reader_data: ReaderUpdate, db_session: AsyncSession = Depends(get_db_session)):
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


@router.delete("/{reader_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(reader_id: int, db_session: AsyncSession = Depends(get_db_session)):
    db_reader = await db_session.get(Reader, reader_id)
    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    await db_session.delete(db_reader)
    await db_session.commit()

    return None