from fastapi import FastAPI
from routers import autors, books, readers
from contextlib import asynccontextmanager
from database import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    yield
    await engine.dispose()


#dark docs
from fastapi_swagger_dark import install
app = FastAPI(lifespan=lifespan, docs_url=None)
install(app)
#end dark docs

#app = FastAPI(title="Library API")


#uvicorn main:app --reload
#http://127.0.0.1:8000/docs

app.include_router(autors.router)
app.include_router(books.router)
app.include_router(readers.router)

@app.get('/')
def root():
    return {"message": "LibraryAPI root"}