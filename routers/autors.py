from fastapi import APIRouter


router = APIRouter(prefix='/authors', tags=["Authors"])

@router.get("/")
def get_all_authors():
    return {"message": "a"}

@router.post("/")
def get_all_authors():
    return {"message": "a"}

