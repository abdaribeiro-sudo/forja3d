import asyncio
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Usa um DB de teste separado
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/forja3d_test")
os.environ.setdefault("ADMIN_PASSWORD", "test_admin")
os.environ.setdefault("AGENT_PASSWORD", "test_agent")
os.environ.setdefault("ORPHAN_PREPARING_MINUTES", "45")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Cria schema no DB de teste e devolve uma sessão limpa por teste."""
    from database import Base

    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncClient:
    from main import app
    from database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
