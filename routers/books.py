from typing import Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database import get_db_session
from schemas.book import BookInput, BookUpdate, BookResponse
from models import Book, Author

router = APIRouter(prefix='/books', tags=["Books"])

#TODO замени селекты на get + selectinload/joinedload посмотри где какой полезен
#TODO думай про mtm для книг и читателей

@router.get("/", status_code=status.HTTP_200_OK, response_model=list[BookResponse])
async def get_books(
        author_name: Optional[str] = Query(None, description="Search by author name"),
        book_title: Optional[str] = Query(None, description="Search by book title"),
        db_session: AsyncSession = Depends(get_db_session)
):

    query = select(Book).join(Book.author)
    if author_name:
        query = query.where(Author.full_name.ilike(f"%{author_name}%"))

    if book_title:
        query = query.where(Book.title.ilike(f"%{book_title}%"))

    query = query.options(joinedload(Book.author))
    result = await db_session.execute(query)
    return result.scalars().all()

    # GET /?name=Иван&book_title=Гарри

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookResponse)
async def create_book(book_data: BookInput, db_session: AsyncSession = Depends(get_db_session)):
    query = select(Author).where(Author.id == book_data.author_id)
    result = await db_session.execute(query)
    author = result.scalar_one_or_none()

    if author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found"
        )


    new_book = Book(**book_data.model_dump())
    db_session.add(new_book)
    await db_session.commit()
    await db_session.refresh(new_book, attribute_names=["id", "author"])
    #new_book.author = author
    return new_book


@router.put(path="/{book_id}", status_code=status.HTTP_200_OK, response_model=BookResponse)
async def put_book(book_id: int, book_data: BookInput, db_session:AsyncSession = Depends(get_db_session)):
    book_query = select(Book).where(Book.id == book_id).options(joinedload(Book.author))
    book_result = await db_session.execute(book_query)
    db_book = book_result.scalar_one_or_none()

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book is not found"
        )

    autor_query = select(Author).where(Author.id == book_data.author_id)
    author_result = await db_session.execute(autor_query)
    author = author_result.scalar_one_or_none()

    if author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author with this id is not found"
        )

    update_data = book_data.model_dump()

    for key, val in update_data.items():
        setattr(db_book, key, val)

    await db_session.commit()

    db_book.author = author

    return db_book

@router.patch(path="/{book_id}", status_code=status.HTTP_200_OK, response_model=BookResponse)
async def patch_book(book_id: int, book_data: BookInput, db_session:AsyncSession = Depends(get_db_session)):
    query = select(Book).where(Book.id == book_id).options(joinedload(Book.author))
    result = await db_session.execute(query)
    db_book = result.scalar_one_or_none()

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book is not found"
        )

    if book_data.author_id:
        autor_query = select(Author).where(Author.id == book_data.author_id)
        author_result = await db_session.execute(autor_query)
        author = author_result.scalar_one_or_none()

        if author is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author with this id is not found"
            )

    update_data = book_data.model_dump(exclude_unset=True)


    for key, val in update_data.items():
        setattr(db_book, key, val)

    await db_session.commit()

    return db_book

@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db_session: AsyncSession = Depends(get_db_session)):
    query = select(Book).where(Book.id == book_id)
    result = await db_session.execute(query)
    db_book = result.scalar_one_or_none()

    if db_book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book is not found"
        )

    await db_session.delete(db_book)
    await db_session.commit()

    return None

