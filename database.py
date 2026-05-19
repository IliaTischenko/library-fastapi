from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base


#load_dotenv()

#local
DATABASE_URL = "postgresql+asyncpg://user:1234@localhost:5432/f_l_db"

#app in docker
#DATABASE_URL ="postgresql+asyncpg://user:1234@db:5432/f_l_db"

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

async def init_db():
    from models import Author, Book, Reader
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session

Base = declarative_base()