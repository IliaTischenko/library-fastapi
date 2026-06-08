from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import get_redis_client
from app.auth_utils import create_first_admin_if_not_exists
from app.database import engine, AsyncSessionLocal
from app.routers import autors, books, readers, users, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        await create_first_admin_if_not_exists(session)
        print("First admin created")
    yield

    redis_client = get_redis_client()
    await redis_client.close()
    await engine.dispose()


# dark docs
from fastapi_swagger_dark import install

app = FastAPI(lifespan=lifespan, docs_url=None)
install(app)
# end dark docs

app.include_router(autors.router)
app.include_router(books.router)
app.include_router(readers.router)
app.include_router(users.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"message": "LibraryAPI root"}
