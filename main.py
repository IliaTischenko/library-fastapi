from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth_utils import create_first_admin_if_not_exists
from database import engine, init_db_local, drop_db, AsyncSessionLocal
from routers import autors, books, readers, admins, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_local()
    async with AsyncSessionLocal() as session:
        await create_first_admin_if_not_exists(session)
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
app.include_router(admins.router)
app.include_router(auth.router)

@app.get('/')
def root():
    return {"message": "LibraryAPI root"}

@app.get('/drop_db')
async def drop():
    await drop_db()
    return {"m":"db dropped"}