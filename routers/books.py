from typing import Optional
from fastapi import APIRouter, status, Query
from schemas.book import BookInput, BookUpdate


router = APIRouter(prefix='/books', tags=["Books"])

@router.get("/", status_code=status.HTTP_200_OK)
def get_books(
        author: Optional[str] = Query(None, description="Search by author name"),
        book_title: Optional[str] = Query(None, description="Search by book title"),
):

    # query = select(Reader)
    #
    # # 2. Каждый фильтр добавляется НЕЗАВИСИМО. Они автоматически объединятся через AND
    # if author:
    #     query = query.where(Reader.name.ilike(f"%{name}%"))
    #
    # if book_title:
    #     query = query.where(Reader.book_title.ilike(f"%{book_title}%"))
    #
    # # 3. Выполняем итоговый запрос. SQLAlchemy сам соберет нужную комбинацию!
    # result = await db.execute(query)
    # return result.scalars().all()

    # GET /?name=Иван&book_title=Гарри
    return {"a"}

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_book(new_book: BookInput):
    return {"message": "alllo"}

@router.put(path="/{book_id}", status_code=status.HTTP_200_OK)
def put_book(new_book: BookInput):
    return {"213"}

@router.patch(path="/{book_id}", status_code=status.HTTP_200_OK)
def patch_book(book_id: int, new_book: BookUpdate):
    return "3"

@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int):
    return {"message": "a"}

