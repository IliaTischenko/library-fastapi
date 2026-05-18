from fastapi import APIRouter, status


router = APIRouter(prefix='/authors', tags=["Authors"])

@router.get("/")
def get_all_authors():
    return {"message": "a"}

@router.post("/{author_id}")
def create_author(author_id: int):
    return {"message": "a"}

@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int):
    return {"message": "a"}

