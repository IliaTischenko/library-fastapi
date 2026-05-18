from fastapi import APIRouter


router = APIRouter(prefix='/books', tags=["Books"])

@router.get("/")
def get_all_books():
    return {"message": "alllo"}

@router.post("/")
def get_all_books():
    return {"message": "alllo"}

