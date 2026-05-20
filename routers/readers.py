from datetime import date
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session
from schemas.reader import ReaderInput, ReaderUpdate, ReaderResponse
from sqlalchemy import select
from models import Reader


router = APIRouter(prefix='/readers', tags=["Readers"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_readers(
        name: Optional[str] = Query(None, description="Search by reader name"),
        book_title: Optional[str] = Query(None, description="Search by book title"),
        start_date: Optional[date] = Query(None, description="Search at date (to end_date)"),
        end_date: Optional[date] = Query(None, description="Search to date (at start_date)"),
        db_session: AsyncSession = Depends(get_db_session)
):

    query = select(Reader)
    if name:
        query = query.where(Reader.full_name.ilike(f"%{name}%"))
    #if book_title:
    if start_date:
        query = query.where(Reader.issue_date >= start_date)
    if end_date:
        query = query.where(Reader.issue_date <= end_date)

    result = await db_session.execute(query)
    readers = result.scalars().all()

    return readers


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ReaderResponse)
async def create_reader(reader_data: ReaderInput, db_session: AsyncSession = Depends(get_db_session)):
    new_reader = Reader(**reader_data.model_dump())
    db_session.add(new_reader)
    await db_session.commit()
    await db_session.refresh(new_reader)
    return new_reader


@router.put("/{reader_id}", status_code=status.HTTP_200_OK, response_model=ReaderResponse)
async def put_reader(reader_id: int, reader_data: ReaderInput, db_session: AsyncSession = Depends(get_db_session)):
    db_reader = await db_session.get(Reader, reader_id)
    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    update_data = reader_data.model_dump()

    for key, val in update_data.items():
        setattr(db_reader, key, val)

    await db_session.commit()
    return db_reader
@router.patch("/{reader_id}", status_code=status.HTTP_200_OK, response_model=ReaderResponse)
async def put_reader(reader_id: int, reader_data: ReaderUpdate, db_session: AsyncSession = Depends(get_db_session)):
    db_reader = await db_session.get(Reader, reader_id)
    if db_reader is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reader with this id is not found"
        )

    update_data = reader_data.model_dump(exclude_unset=True)

    for key, val in update_data.items():
        setattr(db_reader, key, val)

    await db_session.commit()
    return db_reader


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