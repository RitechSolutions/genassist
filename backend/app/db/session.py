<<<<<<< HEAD
from sqlalchemy import create_engine
=======
import asyncio
import logging
import os
from sqlalchemy import create_engine, inspect
>>>>>>> development
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.base import Base

<<<<<<< HEAD
if not settings.DB_ASYNC:
    # Create SQLAlchemy engine
    engine = create_engine(
        settings.DATABASE_URL,
=======
logger = logging.getLogger(__name__)

if not settings.DB_ASYNC:
    # Create SQLAlchemy engine
    engine = create_engine(
        settings.DATABASE_URL_SYNC,
>>>>>>> development
        echo=False,  # Set True for SQL logging in development
        future=True
    )

    # SessionLocal is a factory that creates new Session objects
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True
    )

    # Dependency to get DB session per request
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
else:
    # Create SQLAlchemy engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)


    # SessionLocal is a factory that creates new Session objects
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Dependency to get DB session per request
    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session
            

<<<<<<< HEAD

=======
>>>>>>> development
async def cold_start_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    from .seed.seed import seed_data
    async with AsyncSessionLocal() as session:
<<<<<<< HEAD
        await seed_data(session)
=======
        await seed_data(session)


async def get_all_table_names_async():
    """Helper to run synchronous sqlalchemy_inspect tasks in an async context."""
    def sync_get_table_names(conn):
        # Create inspector within the sync context provided by run_sync
        inspector = inspect(conn)
        return inspector.get_table_names()

    async with engine.begin() as conn:
        all_tables = await conn.run_sync(sync_get_table_names)
        return all_tables

async def run_db_init_actions():
    """
    Handles database initialization
    """

    all_table_names = await get_all_table_names_async()
    print(f"Detected tables: {all_table_names}")

    if settings.CREATE_DB or "users" not in all_table_names:
        await cold_start_db()
>>>>>>> development
