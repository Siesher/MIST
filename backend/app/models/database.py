"""SQLAlchemy async engine and session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.app.config import backend_settings

engine = create_async_engine(
    backend_settings.DATABASE_URL,
    echo=backend_settings.DEBUG,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables (for development). Use Alembic migrations in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Лёгкая идемпотентная миграция (в репо нет alembic): добавить колонку
        # messages.citations_json в существующую БД, если её ещё нет.
        try:
            res = await conn.exec_driver_sql("PRAGMA table_info(messages)")
            cols = {row[1] for row in res}
            if "citations_json" not in cols:
                await conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN citations_json TEXT")
        except Exception:
            pass


async def close_db() -> None:
    """Dispose the engine on shutdown."""
    await engine.dispose()
