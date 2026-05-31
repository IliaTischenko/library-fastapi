import asyncio
import pytest
from unittest.mock import patch, AsyncMock
import pytest_asyncio

from fastapi import HTTPException, status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.auth_utils import RoleChecker
from app.main import app
from app.database import Base, get_db_session

DATABASE_URL = f"postgresql+asyncpg://postgres:postgres@test_db:5432/library_test"



@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True
    )

    yield engine

    await engine.dispose()

@pytest_asyncio.fixture(scope="session")
async def async_session_test(test_engine):
    AsyncSessionTest = async_sessionmaker(
        bind = test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    yield AsyncSessionTest


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_test_db(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def get_test_db_session(async_session_test):
    async with async_session_test() as session:
        yield session







@pytest_asyncio.fixture(scope="function")
async def client(async_session_test):
    async def _override_get_db_session():
        async with async_session_test() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session


    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()