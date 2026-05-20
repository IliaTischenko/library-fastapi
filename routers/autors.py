
from typing import Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException
from schemas.author import AuthorInput, AuthorUpdate, AuthorResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db_session
from models import Author


router = APIRouter(prefix='/authors', tags=["Authors"])

@router.get("/", status_code=status.HTTP_200_OK, response_model=list[AuthorResponse])
async def get_authors(
        author_name: Optional[str] = Query(None, description="Search by name"),
        country: Optional[str] = Query(None, description="Search by country"),
        db_session: AsyncSession = Depends(get_db_session)
):
    query = select(Author)
    if author_name:
        query = query.where(Author.full_name.ilike(f"%{author_name}%"))

    if country:
        query = query.where(Author.country.ilike(country))

    result = await db_session.execute(query)
    authors = result.scalars().all()
    return authors


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AuthorResponse)
async def create_author(author_data: AuthorInput, db_session: AsyncSession = Depends(get_db_session)):
    new_author = Author(**author_data.model_dump())
    db_session.add(new_author)
    await db_session.commit()
    await db_session.refresh(new_author)
    return new_author


@router.put(path="/{author_id}", status_code=status.HTTP_200_OK, response_model=AuthorResponse)
async def put_author(author_id: int, author_data: AuthorInput, db_session: AsyncSession = Depends(get_db_session)):
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
    await db_session.refresh(db_author)

    return db_author


@router.patch(path="/{author_id}", status_code=status.HTTP_200_OK)
async def patch_author(author_id: int, author_data: AuthorUpdate, db_session: AsyncSession = Depends(get_db_session)):
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


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_author(author_id: int, db_session: AsyncSession = Depends(get_db_session)):
    db_author = await db_session.get(Author, author_id)

    if db_author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author is not found"
        )

    await db_session.delete(db_author)
    await db_session.commit()

    return None


