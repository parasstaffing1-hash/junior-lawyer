import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.base import Base
from app.models.legal_corpus import Statute, StatuteSection, LegalSource
from app.core.config import settings

async def init_bare_acts_db():
    print(f"Connecting to {settings.database_url}")
    engine = create_async_engine(settings.database_url, echo=True)
    
    async with engine.begin() as conn:
        print("Creating ONLY Bare Acts tables (Statute, StatuteSection, LegalSource)...")
        # Just create the tables we need for KanoonGPT
        tables = [LegalSource.__table__, Statute.__table__, StatuteSection.__table__]
        await conn.run_sync(Base.metadata.create_all, tables=tables)
        
    print("Bare Acts tables created successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_bare_acts_db())
