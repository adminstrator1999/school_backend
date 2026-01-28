"""Test configuration and fixtures."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.permissions import Role
from app.core.security import get_password_hash
from app.models.user import User
from main import app

# Test database URL - use a separate test database
# When running in docker, use db-test service; locally, use port 5433
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "db:5432/school_accounting", "db-test:5432/school_accounting_test"
).replace(
    "localhost:5432/school_accounting", "localhost:5433/school_accounting_test"
)

# Create test engine with NullPool to avoid connection issues
test_engine = create_async_engine(
    TEST_DATABASE_URL, 
    echo=False,
    poolclass=NullPool,  # Use NullPool for tests to avoid connection issues
)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override database dependency for tests."""
    async with test_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def setup_database() -> AsyncGenerator[None, None]:
    """Create test database tables before each test that needs it."""
    # Override the dependency
    app.dependency_overrides[get_db] = override_get_db
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Clean up override
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def db(setup_database: None) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for tests."""
    async with test_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(setup_database: None) -> AsyncGenerator[AsyncClient, None]:
    """Get async HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def owner_user(db: AsyncSession) -> User:
    """Create an owner user for tests."""
    user = User(
        phone_number="+998901111111",
        password_hash=get_password_hash("password123"),
        first_name="Owner",
        last_name="User",
        role=Role.OWNER,
        school_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    yield user


@pytest_asyncio.fixture
async def superuser(db: AsyncSession) -> User:
    """Create a superuser for tests."""
    user = User(
        phone_number="+998902222222",
        password_hash=get_password_hash("password123"),
        first_name="Super",
        last_name="User",
        role=Role.SUPERUSER,
        school_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    yield user


@pytest_asyncio.fixture
async def owner_token(client: AsyncClient, owner_user: User) -> str:
    """Get auth token for owner user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone_number": "+998901111111", "password": "password123"},
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def superuser_token(client: AsyncClient, superuser: User) -> str:
    """Get auth token for superuser."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone_number": "+998902222222", "password": "password123"},
    )
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    """Create authorization header."""
    return {"Authorization": f"Bearer {token}"}
