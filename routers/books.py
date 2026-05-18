from fastapi import APIRouter, status


router = APIRouter(prefix='/books', tags=["Books"])

@router.get("/")
def get_all_books():
    return {"message": "alllo"}

@router.post("/{book_id}")
def create_book(book_id: int):
    return {"message": "alllo"}

@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int):
    return {"message": "a"}

