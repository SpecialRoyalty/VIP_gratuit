from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


def async_url(url: str) -> str:
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if url.startswith('postgresql://'):
        return 'postgresql+asyncpg://' + url[len('postgresql://'):]
    return url


engine = create_async_engine(async_url(settings.database_url), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    from .models import CampaignReferral

    def create_schema(conn):
        Base.metadata.create_all(conn)
        table = CampaignReferral.__table__
        if 'created_at' not in {col['name'] for col in inspect(conn).get_columns(table.name)}:
            column_type = table.c.created_at.type.compile(dialect=conn.dialect)
            conn.exec_driver_sql(f'ALTER TABLE {table.name} ADD COLUMN created_at {column_type}')

    async with engine.begin() as conn:
        await conn.run_sync(create_schema)
