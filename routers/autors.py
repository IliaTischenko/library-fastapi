from typing import Optional
from fastapi import APIRouter, status, Query, Depends
from schemas.author import AuthorInput, AuthorUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db_session


router = APIRouter(prefix='/authors', tags=["Authors"])

@router.get("/", status_code=status.HTTP_200_OK)
def get_authors(
        name: Optional[str] = Query(None, description="Search by name"),
        book_title: Optional[str] = Query(None, description="Search by book title")
):
    # query = select(Reader)
    #
    # # 2. Каждый фильтр добавляется НЕЗАВИСИМО. Они автоматически объединятся через AND
    # if name:
    #     query = query.where(Reader.name.ilike(f"%{name}%"))
    #
    # if book_title:
    #     query = query.where(Reader.book_title.ilike(f"%{book_title}%"))
    #
    # # 3. Выполняем итоговый запрос. SQLAlchemy сам соберет нужную комбинацию!
    # result = await db.execute(query)
    # return result.scalars().all()
    return {"all"}

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_author(author_data: AuthorInput, db_session: AsyncSession = Depends(get_db_session)):

    return {"message": "a"}

@router.put(path="/{author_id}", status_code=status.HTTP_200_OK)
def put_author(new_author: AuthorInput):
    return {"213"}

@router.patch(path="/{author_id}", status_code=status.HTTP_200_OK)
def patch_author(author_id: int, new_author: AuthorUpdate):
    return "3"

@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int):
    return {"message": "a"}


