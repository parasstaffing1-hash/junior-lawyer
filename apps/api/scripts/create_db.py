import asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.base import Base
from app import models
from app.core.config import settings
from app.db.url import prepare_database_url

async def init_db():
    target = prepare_database_url(settings.database_url)
    # Host and database only — a connection string carries the password.
    safe = make_url(target.url).render_as_string(hide_password=True)
    print(f"Connecting to {safe}")
    engine = create_async_engine(target.url, echo=True, connect_args=target.connect_args)
    
    async with engine.begin() as conn:
        print("Dropping all tables...")
        # Since it's a new db with corrupted alembic state, drop all and recreate
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating all tables from scratch...")
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database tables created successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
