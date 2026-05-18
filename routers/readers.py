from fastapi import APIRouter


router = APIRouter(prefix='/readers', tags=["Readers"])

@router.get("/")
def get_all_members():
    return {"message": "alllo"}

@router.post("/")
def get_all_members():
    return {"message": "alllo"}