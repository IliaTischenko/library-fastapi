from typing import Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload, contains_eager

from database import get_db_session
from schemas import BookInput, BookUpdate, BookResponse, BookResponseShort
from models import Book, Author, Reader

router = APIRouter(prefix='/books', tags=["Books"])


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[BookResponseShort])
async def get_books(
        author_name: Optional[str] = Query(None, description="Search by author name"),
        book_title: Optional[str] = Query(None, description="Search by book title"),
        db_session: AsyncSession = Depends(get_db_session)
):

    query = select(Book)
    if author_name:
        query = query.join(Book.author).where(Author.full_name.ilike(f"%{author_name}%"))
        query = query.options(contains_eager(Book.author))
    else:
        query = query.options(joinedload(Book.author))

    if book_title:
        query = query.where(Book.title.ilike(f"%{book_title}%"))

    result = await db_session.execute(query)
    return result.scalars().all()


@router.get("/{book_id}", status_code=status.HTTP_200_OK, response_model=BookResponse)
async def get_book_detail(book_id: int, db_session: AsyncSession = Depends(get_db_session)):
    db_book = await db_session.get(
        Book,
        book_id,
        options=[selectinload(Book.readers), joinedload(Book.author)]
    )
    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book with this id is not found"
        )

    return db_book



@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookResponse)
async def create_book(book_data: BookInput, db_session: AsyncSession = Depends(get_db_session)):
    db_author = await db_session.get(Author, book_data.author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found"
        )


    data_dict = book_data.model_dump()
    readers_ids = data_dict.pop("readers_ids", [])
    new_book = Book(**data_dict)

    if readers_ids:
        query = select(Reader).where(Reader.id.in_(readers_ids))
        result = await db_session.execute(query)
        readers = result.scalars().all()

        new_book.readers = readers


    db_session.add(new_book)

    await db_session.commit()
    await db_session.refresh(new_book)

    result = await db_session.execute(
        select(Book)
        .options(selectinload(Book.readers), joinedload(Book.author))
        .where(Book.id == new_book.id)
    )
    book_with_relations = result.scalar_one()

    return book_with_relations





@router.put(path="/{book_id}", status_code=status.HTTP_200_OK, response_model=BookResponse)
async def put_book(book_id: int, book_data: BookInput, db_session:AsyncSession = Depends(get_db_session)):
    db_book = await db_session.get(
        Book,
        book_id,
        options=[selectinload(Book.readers)]
    )

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book is not found"
        )

    db_author = await db_session.get(Author, book_data.author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found"
        )

    update_data = book_data.model_dump()
    readers_ids = update_data.pop("readers_ids", [])


    if readers_ids:
        query = select(Reader).where(Reader.id.in_(readers_ids))
        result = await db_session.execute(query)
        readers = result.scalars().all()
        db_book.readers = readers


    for key, val in update_data.items():
        setattr(db_book, key, val)

    await db_session.commit()
    #db_book.author = db_author

    result = await db_session.execute(
        select(Book)
        .options(selectinload(Book.readers), joinedload(Book.author))
        .where(Book.id == book_id)
    )

    book_with_relations = result.scalar_one()

    return book_with_relations


@router.patch(path="/{book_id}", status_code=status.HTTP_200_OK, response_model=BookResponse)
async def patch_book(book_id: int, book_data: BookUpdate, db_session:AsyncSession = Depends(get_db_session)):
    db_book = await db_session.get(
        Book,
        book_id,
        options=[selectinload(Book.readers)]
        )

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book is not found"
        )

    if book_data.author_id:
        db_author = await db_session.get(Author, book_data.author_id)

        if db_author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author with this id is not found"
            )

    update_data = book_data.model_dump(exclude_unset=True)
    readers_ids = update_data.pop("readers_ids", [])

    if readers_ids:
        query = select(Reader).where(Reader.id.in_(readers_ids))
        result = await db_session.execute(query)
        readers = result.scalars().all()
        db_book.readers = readers


    for key, val in update_data.items():
        setattr(db_book, key, val)

    await db_session.commit()

    result = await db_session.execute(
        select(Book)
        .options(selectinload(Book.readers), joinedload(Book.author))
        .where(Book.id == book_id)
    )

    book_with_relations = result.scalar_one()

    return book_with_relations



@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db_session: AsyncSession = Depends(get_db_session)):
    db_book = await db_session.get(Book, book_id)

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book is not found"
        )

    await db_session.delete(db_book)
    await db_session.commit()

    return None

