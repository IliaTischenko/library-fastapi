import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base, get_db_session


TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@test_db:5432/library_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(bind=engine, expire_on_commit=False, class_= AsyncSession)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Позволяет использовать сессию БД прямо в коде теста для создания фейковых данных"""
    async with async_session_test() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Создает тестового клиента и подменяет основную БД на тестовую"""

    # Внутренняя функция-зависимость для подмены
    async def _override_get_db():
        async with async_session_test() as session:
            yield session

    # Магия FastAPI: временно подменяем зависимость во всем приложении
    app.dependency_overrides[get_db_session] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # После завершения теста убираем подмену
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
    ) as client:
        yield client