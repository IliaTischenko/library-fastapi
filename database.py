import os

from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession



load_dotenv()
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST") #db/localhost
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")


#local old worked
#DATABASE_URL = "postgresql+asyncpg://user:1234@localhost:5432/f_l_db"

#app in docker
#DATABASE_URL ="postgresql+asyncpg://user:1234@db:5432/f_l_db"

DATABASE_URL = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind = engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db_local():
    from models import Author, Book, Reader
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    from models import Author, Book, Reader

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session

Base = declarative_base()