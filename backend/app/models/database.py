"""SQLAlchemy async engine and session factory."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.app.config import backend_settings

engine = create_async_engine(
    backend_settings.DATABASE_URL,
    echo=backend_settings.DEBUG,
)

if backend_settings.DATABASE_URL.startswith("sqlite"):
    # SQLite is single-writer; with the stock config (rollback journal,
    # busy_timeout=0) concurrent users collide instantly ("database is locked")
    # and pile up under async fan-out. WAL lets readers run alongside one writer,
    # busy_timeout makes a writer WAIT for the lock instead of failing, and
    # synchronous=NORMAL is the safe+fast pairing with WAL. PRAGMAs are
    # connection-scoped, so set them on every new connection.
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_concurrency_pragmas(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


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
