from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.evidence import (
    BundleCreate, BundleRead, EvidenceDashboard, EvidenceGraphRead, EvidenceItemRead, EvidenceItemUpdate,
    ExhibitCreate, ExhibitRead, ExhibitUpdate, GapRead, GapUpdate, IssueCreate, IssueLinkCreate, IssueLinkRead,
    IssueRead, IssueStandingRead, PrepQuestionCreate, PrepQuestionRead, WitnessCreate, WitnessLinkCreate,
    WitnessLinkRead, WitnessRead,
)
from app.services.evidence import service
from app.services.evidence import standing as standing_service
from app.services.security.context import ActorContext
from app.services.security.dependencies import require_actor

router=APIRouter(prefix="/evidence",tags=["evidence-and-litigation-discovery"])

@router.get("/matters/{matter_id}/dashboard",response_model=EvidenceDashboard)
async def dashboard(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return EvidenceDashboard(**await service.dashboard(db,actor,matter_id))

@router.post("/matters/{matter_id}/rebuild")
async def rebuild(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return await service.rebuild_matter(db,actor,matter_id)

@router.get("/matters/{matter_id}/items",response_model=list[EvidenceItemRead])
async def items(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [EvidenceItemRead.model_validate(r) for r in await service.list_items(db,actor,matter_id)]

@router.patch("/items/{item_id}",response_model=EvidenceItemRead)
async def patch_item(item_id:UUID,payload:EvidenceItemUpdate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return EvidenceItemRead.model_validate(await service.update_item(db,actor,item_id,payload))

@router.get("/matters/{matter_id}/issues",response_model=list[IssueRead])
async def issues(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [IssueRead.model_validate(r) for r in await service.list_issues(db,actor,matter_id)]

@router.post("/matters/{matter_id}/issues",response_model=IssueRead,status_code=201)
async def create_issue(matter_id:UUID,payload:IssueCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return IssueRead.model_validate(await service.create_issue(db,actor,matter_id,payload))

@router.get("/matters/{matter_id}/issue-links",response_model=list[IssueLinkRead])
async def issue_links(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [IssueLinkRead.model_validate(r) for r in await service.list_links(db,actor,matter_id)]

@router.post("/items/{item_id}/issues",response_model=IssueLinkRead,status_code=201)
async def link_issue(item_id:UUID,payload:IssueLinkCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return IssueLinkRead.model_validate(await service.link_issue(db,actor,item_id,payload))

@router.get("/matters/{matter_id}/witnesses",response_model=list[WitnessRead])
async def witnesses(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [WitnessRead.model_validate(r) for r in await service.list_witnesses(db,actor,matter_id)]

@router.post("/matters/{matter_id}/witnesses",response_model=WitnessRead,status_code=201)
async def create_witness(matter_id:UUID,payload:WitnessCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return WitnessRead.model_validate(await service.create_witness(db,actor,matter_id,payload))

@router.get("/matters/{matter_id}/witness-links",response_model=list[WitnessLinkRead])
async def witness_links(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [WitnessLinkRead.model_validate(r) for r in await service.list_witness_links(db,actor,matter_id)]

@router.post("/witnesses/{witness_id}/evidence",response_model=WitnessLinkRead,status_code=201)
async def link_witness(witness_id:UUID,payload:WitnessLinkCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return WitnessLinkRead.model_validate(await service.link_witness(db,actor,witness_id,payload))

@router.get("/matters/{matter_id}/gaps",response_model=list[GapRead])
async def gaps(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [GapRead.model_validate(r) for r in await service.list_gaps(db,actor,matter_id)]

@router.patch("/gaps/{gap_id}",response_model=GapRead)
async def patch_gap(gap_id:UUID,payload:GapUpdate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return GapRead.model_validate(await service.update_gap(db,actor,gap_id,payload.status))

@router.get("/matters/{matter_id}/graph",response_model=EvidenceGraphRead)
async def graph(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return EvidenceGraphRead(**await service.graph(db,actor,matter_id))

@router.get("/matters/{matter_id}/standing",response_model=list[IssueStandingRead])
async def standing(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    """Per-issue rollup over the evidence graph. Describes the file as recorded,
    not the likely outcome."""
    return await standing_service.issue_standing(db,actor,matter_id)

@router.get("/matters/{matter_id}/exhibits",response_model=list[ExhibitRead])
async def exhibits(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [ExhibitRead.model_validate(r) for r in await service.list_exhibits(db,actor,matter_id)]

@router.post("/matters/{matter_id}/exhibits",response_model=ExhibitRead,status_code=201)
async def create_exhibit(matter_id:UUID,payload:ExhibitCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return ExhibitRead.model_validate(await service.create_exhibit(db,actor,matter_id,payload))

@router.patch("/exhibits/{exhibit_id}",response_model=ExhibitRead)
async def patch_exhibit(exhibit_id:UUID,payload:ExhibitUpdate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return ExhibitRead.model_validate(await service.update_exhibit(db,actor,exhibit_id,payload))

@router.get("/witnesses/{witness_id}/prep",response_model=list[PrepQuestionRead])
async def prep(witness_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [PrepQuestionRead.model_validate(r) for r in await service.list_prep_questions(db,actor,witness_id)]

@router.post("/witnesses/{witness_id}/prep",response_model=PrepQuestionRead,status_code=201)
async def add_prep(witness_id:UUID,payload:PrepQuestionCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return PrepQuestionRead.model_validate(await service.add_prep_question(db,actor,witness_id,payload))

@router.post("/witnesses/{witness_id}/prep/generate",response_model=list[PrepQuestionRead])
async def generate_prep(witness_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [PrepQuestionRead.model_validate(r) for r in await service.generate_prep_questions(db,actor,witness_id)]

@router.get("/matters/{matter_id}/bundles",response_model=list[BundleRead])
async def bundles(matter_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return [BundleRead.model_validate(r) for r in await service.list_bundles(db,actor,matter_id)]

@router.post("/matters/{matter_id}/bundles",response_model=BundleRead,status_code=201)
async def create_bundle(matter_id:UUID,payload:BundleCreate,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return BundleRead.model_validate(await service.create_bundle(db,actor,matter_id,payload))

@router.post("/bundles/{bundle_id}/finalize",response_model=BundleRead)
async def finalize_bundle(bundle_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    return BundleRead.model_validate(await service.finalize_bundle(db,actor,bundle_id))

@router.get("/bundles/{bundle_id}/download")
async def download_bundle(bundle_id:UUID,actor:ActorContext=Depends(require_actor),db:AsyncSession=Depends(get_db)):
    row,path=await service.bundle_file(db,actor,bundle_id)
    return FileResponse(path=path,filename=f"{row.title}.zip",media_type="application/zip")
