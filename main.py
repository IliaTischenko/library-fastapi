from fastapi import FastAPI
from routers import autors, books, readers

app = FastAPI(title="Library API")
#uvicorn main:app --reload

app.include_router(autors.router)
app.include_router(books.router)
app.include_router(readers.router)

@app.get('/')
def root():
    return {"message": "LibraryAPI root"}