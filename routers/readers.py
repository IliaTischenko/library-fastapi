from datetime import date
from typing import Optional
from fastapi import APIRouter, status, Query
from schemas.reader import ReaderInput, ReaderUpdate


router = APIRouter(prefix='/readers', tags=["Readers"])

@router.get("/", status_code=status.HTTP_200_OK)
def get_readers(
        name: Optional[str] = Query(None, description="Search by reader name"),
        book_title: Optional[str] = Query(None, description="Search by book title"),
        start_date: Optional[date] = Query(None, description="Search at date (to end_date)"),
        end_date: Optional[date] = Query(None, description="Search to date (at start_date)"),
):

    # query = select(Reader)
    # # 2. Каждый фильтр добавляется НЕЗАВИСИМО. Они автоматически объединятся через AND
    # if name:
    #     query = query.where(Reader.name.ilike(f"%{name}%"))
    #
    # if book_title:
    #     query = query.where(Reader.book_title.ilike(f"%{book_title}%"))
    #
    # if start_date:
    #     query = query.where(Reader.registration_date >= start_date)
    #
    # if end_date:
    #     query = query.where(Reader.registration_date <= end_date)
    #
    # # 3. Выполняем итоговый запрос. SQLAlchemy сам соберет нужную комбинацию!
    # result = await db.execute(query)
    # return result.scalars().all()
    return {"aaa"}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_reader(new_reader: ReaderInput):
    return {"message": "alllo"}

@router.put("/{reader_id}", status_code=status.HTTP_200_OK)
def put_reader(reader_id: int):
    pass

@router.patch("/{reader_id}", status_code=status.HTTP_200_OK)
def put_reader(reader_id: int, new_reader: ReaderUpdate):
    pass

@router.delete("/{reader_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(reader_id: int):
    return {"message": "a"}