from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.base import Base

if not settings.DB_ASYNC:
    # Create SQLAlchemy engine
    engine = create_engine(
        settings.DATABASE_URL_SYNC,
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
            


async def cold_start_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    from .seed.seed import seed_data
    async with AsyncSessionLocal() as session:
        await seed_data(session)