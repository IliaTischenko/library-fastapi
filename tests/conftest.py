from typing import AsyncGenerator, Iterator, Callable, Any, NoReturn


import pytest
import pytest_asyncio

from fastapi import HTTPException, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)

from app.auth_utils import RoleChecker
from app.main import app
from app.database import Base, get_db_session

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@test_db:5432/library_test"

pytest_plugins = ["tests.test_books", "tests.test_users", "tests.test_authors"]


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def async_session_test(
    test_engine: AsyncEngine,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    AsyncSessionTest = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    yield AsyncSessionTest


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_test_db(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def get_test_db_session(async_session_test) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session


@pytest.fixture(scope="function")
def setup_auth() -> Iterator[Callable[[dict[str, Any]], dict[str, Any] | NoReturn]]:
    """
    Фикстура заглушка для поведения авторизации
    при HTTPexeption - RoleChecker выбросит соответсвующую ошибку
    при dict успешная авторизация с указанными payloads
    """
    captured_keys = []

    def _factory(setup_behavior):
        def create_mock(instance: RoleChecker):
            async def mock_call(
                access_token: str | None = None,
            ) -> dict[str, Any] | NoReturn:
                if not setup_behavior["token_str"]:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Not authenticated (Cookie missing/Token in blacklist)",
                    )

                if (
                    instance.required_roles
                    and setup_behavior["role"] not in instance.required_roles
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient rights",
                    )

                return setup_behavior

            return mock_call

        keys = [
            RoleChecker(),
            RoleChecker(("admin",)),
            RoleChecker(
                (
                    "admin",
                    "reader",
                )
            ),
        ]

        for key in keys:
            app.dependency_overrides[key] = create_mock(key)
            captured_keys.append(key)

    yield _factory

    for key in captured_keys:
        app.dependency_overrides.pop(key, None)


@pytest_asyncio.fixture(scope="function")
async def client(
    async_session_test: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_test() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
