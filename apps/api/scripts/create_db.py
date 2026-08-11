import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.base import Base
from app import models
from app.core.config import settings

async def init_db():
    print(f"Connecting to {settings.database_url}")
    engine = create_async_engine(settings.database_url, echo=True)
    
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
