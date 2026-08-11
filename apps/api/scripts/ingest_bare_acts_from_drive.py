import asyncio
import json
import uuid
import sys
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings
from app.db.session import async_sessionmaker, engine
from app.models.legal_corpus import Statute, StatuteSection, LegalSource
from app.services.documents.storage import _gdrive_service

async def ingest_from_drive(file_id: str):
    print(f"Connecting to Google Drive to download dataset {file_id}...")
    try:
        service = _gdrive_service()
        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")
        
        fh.seek(0)
        data = json.load(fh)
    except Exception as e:
        print(f"Failed to download or parse JSON from Google Drive: {e}")
        return

    print(f"Successfully loaded {len(data)} Bare Acts from Drive.")
    
    AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        print("Ensuring default LegalSource exists...")
        # Create a default source for the dataset
        result = await db.execute(select(LegalSource).where(LegalSource.code == 'KANOON_GPT_DRIVE'))
        source = result.scalars().first()
        if not source:
            source = LegalSource(
                id=uuid.uuid4(),
                code='KANOON_GPT_DRIVE',
                name='KanoonGPT Google Drive Dataset',
                jurisdiction='India',
                official=False,
                kind='dataset',
                enabled=True,
                metadata_json={}
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            
        print("Starting ingestion...")
        for act_data in data:
            # Check if act already exists
            external_id = act_data.get("id") or str(uuid.uuid4())
            result = await db.execute(select(Statute).where(Statute.external_id == external_id))
            statute = result.scalars().first()
            
            if not statute:
                print(f"Ingesting: {act_data.get('title')}")
                statute = Statute(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    external_id=external_id,
                    title_en=act_data.get("title", "Unknown"),
                    act_year=act_data.get("year", 2000),
                    jurisdiction=act_data.get("type", "Central"),
                    is_active=True,
                    metadata_json={}
                )
                db.add(statute)
                await db.flush()
                
                # Ingest sections
                sections = act_data.get("sections", [])
                for idx, section_data in enumerate(sections):
                    section = StatuteSection(
                        id=uuid.uuid4(),
                        statute_id=statute.id,
                        section_key=f"{statute.external_id}_sec_{section_data.get('section_number')}",
                        section_number=section_data.get("section_number", str(idx+1)),
                        provision_type="section",
                        heading_en=section_data.get("title", ""),
                        text_en=section_data.get("text", ""),
                        normalized_text=section_data.get("text", "").lower(),
                        sort_order=idx + 1,
                        metadata_json={
                            "simplified_explanation": section_data.get("simplified_explanation"),
                            "audio_url": section_data.get("audio_url")
                        }
                    )
                    db.add(section)
                    
            await db.commit()
            
        print("Ingestion complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.ingest_bare_acts_from_drive <google_drive_file_id>")
        sys.exit(1)
    asyncio.run(ingest_from_drive(sys.argv[1]))
