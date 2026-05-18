from fastapi import APIRouter, status


router = APIRouter(prefix='/readers', tags=["Readers"])

@router.get("/")
def get_all_readers():
    return {"message": "alllo"}

@router.post("/{reader_id}")
def create_reader(reader_id: int):
    return {"message": "alllo"}

@router.delete("/{reader_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(reader_id: int):
    return {"message": "a"}