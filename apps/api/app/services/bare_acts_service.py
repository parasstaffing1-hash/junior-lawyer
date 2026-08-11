import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.legal_corpus import Statute, StatuteSection

class BareActsService:
    async def get_all_acts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Return a list of all available acts without full section text for browsing."""
        stmt = select(Statute).where(Statute.is_active == True)
        result = await db.execute(stmt)
        acts = result.scalars().all()
        
        return [
            {
                "id": str(act.id),
                "title": act.title_en,
                "year": act.act_year,
                "type": act.jurisdiction,
                # We won't eagerly count sections here for performance, default to 0
                "section_count": len(act.sections) if act.sections else 0
            }
            for act in acts
        ]
        
    async def get_act_by_id(self, db: AsyncSession, act_id: str) -> Optional[Dict[str, Any]]:
        """Return full details of a specific act including all sections."""
        try:
            act_uuid = uuid.UUID(act_id)
        except ValueError:
            # Maybe the frontend is passing string IDs like "contract", try external_id fallback
            stmt = select(Statute).options(selectinload(Statute.sections)).where(Statute.external_id == act_id)
            result = await db.execute(stmt)
            act = result.scalars().first()
            if not act:
                return None
        else:
            stmt = select(Statute).options(selectinload(Statute.sections)).where(Statute.id == act_uuid)
            result = await db.execute(stmt)
            act = result.scalars().first()
            if not act:
                return None
            
        sections = []
        for section in act.sections:
            meta = section.metadata_json or {}
            sections.append({
                "id": str(section.id),
                "section_number": section.section_number,
                "title": section.heading_en,
                "text": section.text_en,
                "simplified_explanation": meta.get("simplified_explanation"),
                "audio_url": meta.get("audio_url")
            })
            
        return {
            "id": str(act.id),
            "title": act.title_en,
            "year": act.act_year,
            "type": act.jurisdiction,
            "sections": sections
        }
        
    async def search_sections(self, db: AsyncSession, query: str) -> List[Dict[str, Any]]:
        """Basic keyword search across all sections for the UI search bar."""
        stmt = select(StatuteSection).options(selectinload(StatuteSection.statute)).where(
            (StatuteSection.heading_en.ilike(f"%{query}%")) |
            (StatuteSection.text_en.ilike(f"%{query}%"))
        ).limit(20)
        
        result = await db.execute(stmt)
        sections = result.scalars().all()
        
        results = []
        for section in sections:
            meta = section.metadata_json or {}
            results.append({
                "act_title": section.statute.title_en if section.statute else "Unknown Act",
                "act_id": str(section.statute_id),
                "id": str(section.id),
                "section_number": section.section_number,
                "title": section.heading_en,
                "text": section.text_en,
                "simplified_explanation": meta.get("simplified_explanation"),
                "audio_url": meta.get("audio_url")
            })
        return results

bare_acts_service = BareActsService()
