from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from difflib import SequenceMatcher
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contract import (
    ClauseSource,
    ClauseTemplate,
    Contract,
    ContractClause,
    ContractRisk,
    ContractRiskLevel,
    ContractRiskProfile,
    ContractRiskStatus,
    ContractStatus,
    ContractVersion,
)
from app.models.matter import Matter
from app.models.security import MatterAccessLevel, OrganizationRole
from app.services.security.context import get_current_actor
from app.services.security.permissions import ROLE_BASE_LEVEL, decide_matter_access, visible_matter_ids
from app.schemas.contract import (
    ClauseUpdate,
    ComparisonClause,
    ContractComparison,
    ContractCreate,
    ContractListItem,
    ContractUpdate,
)
from app.services.contracts.catalog import BUILTIN_CLAUSES, CONTRACT_DEFINITIONS
from app.services.contracts.renderer import build_variables, generate_docx, render_text, resolve_contract_storage_key
from app.services.contracts.rules import evaluate_contract, health_score


async def seed_clause_library(db: AsyncSession) -> int:
    existing = {
        (row.code, row.version)
        for row in (await db.scalars(select(ClauseTemplate))).all()
    }
    created = 0
    for item in BUILTIN_CLAUSES:
        key = (item["code"], item["version"])
        if key in existing:
            continue
        db.add(ClauseTemplate(**item))
        created += 1
    if created:
        await db.commit()
    return created


async def list_clause_library(db: AsyncSession) -> list[ClauseTemplate]:
    await seed_clause_library(db)
    stmt = select(ClauseTemplate).where(ClauseTemplate.active.is_(True)).order_by(
        ClauseTemplate.clause_type, ClauseTemplate.variant_key, ClauseTemplate.version.desc()
    )
    return list((await db.scalars(stmt)).all())


async def get_contract(db: AsyncSession, contract_id: UUID) -> Contract:
    stmt = (
        select(Contract)
        .where(Contract.id == contract_id)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.risks),
            selectinload(Contract.versions),
        )
        .execution_options(populate_existing=True)
    )
    contract = (await db.execute(stmt)).scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    actor = get_current_actor()
    if actor is not None:
        if contract.matter_id:
            decision = await decide_matter_access(db, actor, contract.matter_id, required=MatterAccessLevel.VIEW)
            if not decision.allowed:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
        elif contract.organization_id != actor.organization_id or ROLE_BASE_LEVEL.get(actor.role) is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contract access is not permitted")
    return contract


async def list_contracts(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[ContractListItem]:
    stmt = select(Contract).options(selectinload(Contract.clauses), selectinload(Contract.risks))
    actor = get_current_actor()
    if actor is not None:
        visible = await visible_matter_ids(db, actor)
        conditions = [Contract.organization_id == actor.organization_id]
        if visible:
            conditions.append(Contract.matter_id.in_(visible))
        stmt = stmt.where(or_(*conditions))
    stmt = stmt.order_by(Contract.updated_at.desc()).limit(limit).offset(offset)
    rows = list((await db.scalars(stmt)).unique().all())
    return [
        ContractListItem(
            id=item.id,
            title=item.title,
            contract_type=item.contract_type,
            language=item.language,
            status=item.status,
            risk_profile=item.risk_profile,
            party_a_name=item.party_a_name,
            party_b_name=item.party_b_name,
            health_score=item.health_score,
            clause_count=len(item.clauses),
            open_high_risks=sum(
                1
                for risk in item.risks
                if risk.level == ContractRiskLevel.HIGH and risk.status == ContractRiskStatus.OPEN
            ),
            updated_at=item.updated_at,
        )
        for item in rows
    ]


async def create_contract(db: AsyncSession, payload: ContractCreate) -> Contract:
    actor = get_current_actor()
    if payload.matter_id is not None and await db.get(Matter, payload.matter_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matter not found")
    if actor is not None and payload.matter_id is not None:
        decision = await decide_matter_access(db, actor, payload.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)

    questionnaire = dict(payload.questionnaire_json)
    questionnaire.setdefault("governing_state", payload.governing_state)
    questionnaire.setdefault("effective_date", payload.effective_date.isoformat() if payload.effective_date else None)

    contract = Contract(
        organization_id=actor.organization_id if actor else None,
        created_by_user_id=actor.user_id if actor else None,
        matter_id=payload.matter_id,
        title=payload.title,
        contract_type=payload.contract_type,
        language=payload.language,
        risk_profile=payload.risk_profile,
        jurisdiction=payload.jurisdiction,
        governing_state=payload.governing_state,
        party_a_name=payload.party_a_name,
        party_b_name=payload.party_b_name,
        effective_date=payload.effective_date,
        questionnaire_json=questionnaire,
        metadata_json={
            "drafting_engine": "deterministic_v1",
            "lawyer_review_required": True,
        },
    )
    db.add(contract)
    await db.commit()
    return await get_contract(db, contract.id)


async def _require_contract_work(db: AsyncSession, contract: Contract) -> None:
    actor = get_current_actor()
    if actor is None:
        return
    if contract.matter_id:
        decision = await decide_matter_access(db, actor, contract.matter_id, required=MatterAccessLevel.WORK)
        if not decision.allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
        return
    if contract.organization_id != actor.organization_id or ROLE_BASE_LEVEL.get(actor.role) not in {MatterAccessLevel.WORK, MatterAccessLevel.MANAGE}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contract editing is not permitted")


async def _require_contract_export(db: AsyncSession, contract: Contract) -> None:
    actor = get_current_actor()
    if actor is None:
        return
    if contract.matter_id:
        decision = await decide_matter_access(db, actor, contract.matter_id, required=MatterAccessLevel.VIEW)
        if not decision.allowed or not decision.export_allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contract export is blocked by security policy")
        return
    from app.services.security.service import get_policy
    policy = await get_policy(db, actor.organization_id)
    if contract.organization_id != actor.organization_id or not policy.allow_exports_default:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contract export is blocked by security policy")


async def update_contract(db: AsyncSession, contract_id: UUID, payload: ContractUpdate) -> Contract:
    contract = await get_contract(db, contract_id)
    await _require_contract_work(db, contract)
    data = payload.model_dump(exclude_unset=True)
    questionnaire = data.pop("questionnaire_json", None)
    for field, value in data.items():
        setattr(contract, field, value)
    if questionnaire is not None:
        contract.questionnaire_json = questionnaire
    if "governing_state" in data:
        contract.questionnaire_json = {**contract.questionnaire_json, "governing_state": contract.governing_state}
    if "effective_date" in data:
        contract.questionnaire_json = {
            **contract.questionnaire_json,
            "effective_date": contract.effective_date.isoformat() if contract.effective_date else None,
        }
    if contract.status == ContractStatus.APPROVED:
        contract.status = ContractStatus.DRAFT
        contract.approved_at = None
    await db.commit()
    return await get_contract(db, contract_id)


async def _select_template(
    db: AsyncSession,
    *,
    contract_type: str,
    clause_type: str,
    risk_profile: ContractRiskProfile,
) -> ClauseTemplate:
    await seed_clause_library(db)
    preferred = risk_profile.value
    if preferred not in {"pro_party_a", "pro_party_b"}:
        preferred = "balanced"
    stmt = (
        select(ClauseTemplate)
        .where(ClauseTemplate.clause_type == clause_type, ClauseTemplate.active.is_(True))
        .order_by(ClauseTemplate.version.desc())
    )
    candidates = list((await db.scalars(stmt)).all())
    eligible = [item for item in candidates if contract_type in (item.contract_types_json or [])]
    match = next((item for item in eligible if item.variant_key == preferred), None)
    match = match or next((item for item in eligible if item.variant_key == "balanced"), None)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No clause template available for {clause_type}/{contract_type}",
        )
    return match


async def _replace_risks(db: AsyncSession, contract: Contract) -> int:
    old_statuses = {
        risk.rule_code: risk.status
        for risk in contract.risks
    }
    await db.execute(delete(ContractRisk).where(ContractRisk.contract_id == contract.id))
    await db.flush()

    findings = evaluate_contract(
        contract_type=contract.contract_type.value,
        party_a_name=contract.party_a_name,
        party_b_name=contract.party_b_name,
        governing_state=contract.governing_state,
        questionnaire=contract.questionnaire_json,
        clause_types=[item.clause_type for item in contract.clauses],
        modified_clause_types=[item.clause_type for item in contract.clauses if item.is_modified],
    )
    for finding in findings:
        previous = old_statuses.get(finding.rule_code, ContractRiskStatus.OPEN)
        db.add(
            ContractRisk(
                contract_id=contract.id,
                rule_code=finding.rule_code,
                clause_type=finding.clause_type,
                title=finding.title,
                explanation=finding.explanation,
                level=finding.level,
                status=previous,
                metadata_json=finding.metadata or {},
            )
        )
    contract.health_score = health_score(findings)
    await db.flush()
    return contract.health_score


def _snapshot_clauses(contract: Contract) -> list[dict]:
    variables = build_variables(contract)
    return [
        {
            "clause_code": item.clause_code,
            "clause_type": item.clause_type,
            "variant_key": item.variant_key,
            "position": item.position,
            "title_en": item.title_en,
            "title_hi": item.title_hi,
            "body_en": render_text(item.body_en, variables),
            "body_hi": render_text(item.body_hi, variables),
            "source": item.source.value,
            "is_modified": item.is_modified,
        }
        for item in sorted(contract.clauses, key=lambda clause: clause.position)
    ]


def _snapshot_risks(contract: Contract) -> list[dict]:
    return [
        {
            "rule_code": item.rule_code,
            "clause_type": item.clause_type,
            "title": item.title,
            "explanation": item.explanation,
            "level": item.level.value,
            "status": item.status.value,
        }
        for item in contract.risks
    ]


async def _next_version_number(db: AsyncSession, contract_id: UUID) -> int:
    value = await db.scalar(
        select(func.max(ContractVersion.version_number)).where(ContractVersion.contract_id == contract_id)
    )
    return int(value or 0) + 1


async def _write_version(
    db: AsyncSession,
    contract: Contract,
    *,
    label: str,
) -> ContractVersion:
    version_number = await _next_version_number(db, contract.id)
    filename, storage_key, digest = await asyncio.to_thread(
        generate_docx, contract, version_number=version_number
    )
    contract.generated_filename = filename
    contract.generated_storage_key = storage_key
    version = ContractVersion(
        contract_id=contract.id,
        version_number=version_number,
        label=label,
        questionnaire_json=dict(contract.questionnaire_json),
        clauses_json=_snapshot_clauses(contract),
        risks_json=_snapshot_risks(contract),
        health_score=contract.health_score,
        sha256=digest,
        generated_filename=filename,
        generated_storage_key=storage_key,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def draft_contract(db: AsyncSession, contract_id: UUID) -> tuple[Contract, ContractVersion]:
    contract = await get_contract(db, contract_id)
    await _require_contract_work(db, contract)
    definition = CONTRACT_DEFINITIONS[contract.contract_type.value]

    await db.execute(delete(ContractClause).where(ContractClause.contract_id == contract.id))
    await db.execute(delete(ContractRisk).where(ContractRisk.contract_id == contract.id))
    await db.flush()

    for position, clause_type in enumerate(definition["clauses"], start=1):
        template = await _select_template(
            db,
            contract_type=contract.contract_type.value,
            clause_type=clause_type,
            risk_profile=contract.risk_profile,
        )
        db.add(
            ContractClause(
                contract_id=contract.id,
                clause_template_id=template.id,
                clause_code=template.code,
                clause_type=template.clause_type,
                variant_key=template.variant_key,
                title_en=template.title_en,
                title_hi=template.title_hi,
                body_en=template.body_en,
                body_hi=template.body_hi,
                position=position,
                source=ClauseSource.BUILTIN,
                is_modified=False,
                metadata_json={"template_version": template.version},
            )
        )
    contract.status = ContractStatus.DRAFT
    contract.approved_at = None
    await db.commit()

    contract = await get_contract(db, contract_id)
    await _replace_risks(db, contract)
    await db.commit()
    contract = await get_contract(db, contract_id)
    version = await _write_version(db, contract, label="Deterministic draft")
    return await get_contract(db, contract_id), version


async def review_contract(db: AsyncSession, contract_id: UUID) -> Contract:
    contract = await get_contract(db, contract_id)
    await _require_contract_work(db, contract)
    await _replace_risks(db, contract)
    if contract.status != ContractStatus.APPROVED:
        contract.status = ContractStatus.IN_REVIEW
    await db.commit()
    return await get_contract(db, contract_id)


async def update_clause(
    db: AsyncSession,
    contract_id: UUID,
    clause_id: UUID,
    payload: ClauseUpdate,
) -> Contract:
    contract = await get_contract(db, contract_id)
    await _require_contract_work(db, contract)
    clause = next((item for item in contract.clauses if item.id == clause_id), None)
    if clause is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract clause not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(clause, field, value)
    clause.is_modified = True
    clause.source = ClauseSource.CUSTOM
    contract.status = ContractStatus.IN_REVIEW
    contract.approved_at = None
    await db.commit()
    return await review_contract(db, contract_id)


async def update_risk_status(
    db: AsyncSession,
    contract_id: UUID,
    risk_id: UUID,
    risk_status: ContractRiskStatus,
) -> Contract:
    contract = await get_contract(db, contract_id)
    await _require_contract_work(db, contract)
    risk = next((item for item in contract.risks if item.id == risk_id), None)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract risk not found")
    risk.status = risk_status
    await db.commit()
    return await get_contract(db, contract_id)


async def approve_contract(db: AsyncSession, contract_id: UUID) -> tuple[Contract, ContractVersion]:
    contract = await get_contract(db, contract_id)
    await _require_contract_work(db, contract)
    if not contract.clauses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate and review a contract draft before approval",
        )
    open_high = [
        item
        for item in contract.risks
        if item.level == ContractRiskLevel.HIGH and item.status == ContractRiskStatus.OPEN
    ]
    if open_high:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Resolve or explicitly ignore open high-risk findings before approval",
                "risk_ids": [str(item.id) for item in open_high],
            },
        )
    contract.status = ContractStatus.APPROVED
    contract.approved_at = datetime.now(timezone.utc)
    await db.commit()
    contract = await get_contract(db, contract_id)
    version = await _write_version(db, contract, label="Lawyer-approved")
    return await get_contract(db, contract_id), version


async def list_versions(db: AsyncSession, contract_id: UUID) -> list[ContractVersion]:
    await get_contract(db, contract_id)
    stmt = (
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_number.desc())
    )
    return list((await db.scalars(stmt)).all())


async def get_download_path(db: AsyncSession, contract_id: UUID):
    contract = await get_contract(db, contract_id)
    await _require_contract_export(db, contract)
    if not contract.generated_storage_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generate a draft first")
    path = resolve_contract_storage_key(contract.generated_storage_key)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated DOCX is missing")
    return contract, path


async def compare_contracts(
    db: AsyncSession,
    *,
    left_id: UUID,
    right_id: UUID,
) -> ContractComparison:
    left = await get_contract(db, left_id)
    right = await get_contract(db, right_id)
    left_map = {item.clause_type: item for item in left.clauses}
    right_map = {item.clause_type: item for item in right.clauses}
    rows: list[ComparisonClause] = []
    summary = {"unchanged": 0, "modified": 0, "added": 0, "removed": 0}

    for clause_type in sorted(set(left_map) | set(right_map)):
        l_clause = left_map.get(clause_type)
        r_clause = right_map.get(clause_type)
        if l_clause is None:
            state = "added"
            similarity = 0.0
        elif r_clause is None:
            state = "removed"
            similarity = 0.0
        else:
            similarity = SequenceMatcher(None, l_clause.body_en, r_clause.body_en).ratio()
            state = "unchanged" if similarity >= 0.995 else "modified"
        summary[state] += 1
        rows.append(
            ComparisonClause(
                clause_type=clause_type,
                status=state,
                similarity=round(similarity, 4),
                left_title=l_clause.title_en if l_clause else None,
                right_title=r_clause.title_en if r_clause else None,
                left_text=l_clause.body_en if l_clause else None,
                right_text=r_clause.body_en if r_clause else None,
            )
        )

    return ContractComparison(
        left_contract_id=left.id,
        right_contract_id=right.id,
        summary=summary,
        clauses=rows,
    )
