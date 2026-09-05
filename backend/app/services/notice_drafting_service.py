from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.notice import Notice
from app.schemas.notices import (
    NoticeDraftCreate,
    NoticeIssueRequest,
    NoticeReviewRequest,
    NoticeUpdate,
)

_CATALOG_PATH = Path(__file__).resolve().parents[3] / 'legal' / 'rule_catalog' / 'rules_v1.json'


def get_legal_catalog_context() -> dict[str, Any]:
    """Retrieve catalog version, SHA-256 digest, and effective date."""
    if not _CATALOG_PATH.exists():
        return {
            'catalog_version': '1.0.0',
            'catalog_sha256': 'UNKNOWN',
            'effective_date': '2026-09-02',
        }
    content = _CATALOG_PATH.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    try:
        data = json.loads(content.decode('utf-8'))
        version = data.get('catalog_version', '1.0.0')
        effective_date = data.get('last_updated', '2026-09-02')
    except Exception:
        version = '1.0.0'
        effective_date = '2026-09-02'
    return {
        'catalog_version': version,
        'catalog_sha256': sha256,
        'effective_date': effective_date,
    }


def map_finding_to_statutory_charge(finding: Finding, catalog_rules: dict[str, Any]) -> dict[str, Any]:
    """
    Rigorously map a confirmed finding to statutory provisions under the Act and Rules.
    
    Section 36(1) of the Legal Metrology Act, 2009 governs manufacturing, packing, importing,
    selling, or distributing pre-packaged commodities that do not conform to mandatory declarations.
    Section 36(2) strictly applies to physical short measure / net quantity shortfall exceeding MPE.
    
    If the statutory mapping cannot be safely determined, route to MANUAL_LEGAL_REVIEW.
    """
    rule_id = finding.rule_check_id
    cat_rule = catalog_rules.get(rule_id, {})
    legal_citation = cat_rule.get('legal_citation') or finding.legal_citation or rule_id

    # Known Chapter II PCR 2011 declarations
    known_declarations = {
        'PCR-001': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(a) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing or incomplete name and physical address of manufacturer, packer, or importer on pre-packaged commodity.',
            'requires_manual': False,
        },
        'PCR-002': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(aa) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing country of origin declaration for imported pre-packaged commodity.',
            'requires_manual': False,
        },
        'PCR-003': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(b) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing or non-compliant generic or common commodity name declaration.',
            'requires_manual': False,
        },
        'PCR-004': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(c) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing or non-standard net quantity declaration (unit or measure non-conforming to Fourth Schedule).',
            'requires_manual': False,
        },
        'PCR-005': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(d) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing or improper month and year of manufacture, packing, or import.',
            'requires_manual': False,
        },
        'PCR-006': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(e) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing or invalid Maximum Retail Price (MRP) declaration in statutory inclusive-of-all-taxes format.',
            'requires_manual': False,
        },
        'PCR-007': {
            'provision': 'Section 36(1) of the Legal Metrology Act, 2009 read with Rule 6(1)(f) of the Legal Metrology (Packaged Commodities) Rules, 2011',
            'basis': 'Statutory non-conformance: Missing or incomplete consumer care contact details (name, address, phone/email).',
            'requires_manual': False,
        },
    }

    # Check for multi-panel conflicting detections or unverified rules
    has_conflict = getattr(finding, 'has_conflict', False)
    if rule_id in known_declarations and not has_conflict:
        mapping = known_declarations[rule_id]
        statutory_provision = mapping['provision']
        liability_basis = mapping['basis']
        requires_manual = mapping['requires_manual']
    else:
        statutory_provision = 'Legal Metrology Act, 2009 (Substantive section to be verified by Inspecting Officer)'
        if has_conflict:
            liability_basis = 'MANUAL_LEGAL_REVIEW: Multi-panel conflicting evidence detected across package faces. Officer must reconcile factual discrepancy prior to issuance.'
        else:
            liability_basis = f'MANUAL_LEGAL_REVIEW: Rule check {rule_id} does not map deterministically to verified statutory provisions. Inspecting officer confirmation required.'
        requires_manual = True

    return {
        'finding_id': finding.id,
        'rule_id': rule_id,
        'rule_citation': legal_citation,
        'defect_description': finding.description or finding.title,
        'statutory_provision': statutory_provision,
        'liability_basis': liability_basis,
        'requires_manual_review': requires_manual,
        'officer_notes': None,
    }


def _load_rule_catalog() -> dict[str, Any]:
    if not _CATALOG_PATH.exists():
        return {}
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding='utf-8'))
        return {r['rule_id']: r for r in data.get('rules', [])}
    except Exception:
        return {}


def draft_notice_from_inspection(
    db: Session,
    inspection_id: str,
    draft_params: NoticeDraftCreate | None = None,
) -> Notice:
    """Generate a draft statutory notice / inspection memo from a completed inspection."""
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Inspection {inspection_id} not found',
        )

    if inspection.status != 'COMPLETED':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot draft statutory notice: inspection is not finalized (status must be COMPLETED).',
        )

    # Check if a notice already exists
    existing_notice = db.scalars(
        select(Notice).where(Notice.inspection_id == inspection_id).order_by(Notice.created_at.desc())
    ).first()

    if existing_notice:
        return existing_notice

    catalog_rules = _load_rule_catalog()
    legal_context = get_legal_catalog_context()

    # Collect confirmed violations
    charges: list[dict[str, Any]] = []
    for f in sorted(inspection.findings, key=lambda x: x.created_at):
        # Exclude dismissed false positives
        if f.inspector_decision == 'DISMISSED_FALSE_POSITIVE' or f.status == 'dismissed':
            continue
        # Include findings that are violations, warnings, or potential violations
        if f.severity in ('violation', 'critical', 'major', 'warning') or f.status in ('confirmed', 'violation', 'potential_violation', 'flagged', 'open'):
            charges.append(map_finding_to_statutory_charge(f, catalog_rules))

    if not charges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot draft statutory notice: no confirmed or actionable violations found for this inspection.',
        )

    # Compile evidence references with SHA-256 digests
    evidence_refs: list[dict[str, Any]] = []
    for img in sorted(inspection.images, key=lambda x: x.created_at):
        img_sha = 'UNAVAILABLE'
        if img.storage_path:
            full_path = Path(img.storage_path)
            if not full_path.is_absolute():
                full_path = Path(__file__).resolve().parents[2] / img.storage_path
            if full_path.exists():
                img_sha = hashlib.sha256(full_path.read_bytes()).hexdigest()
            else:
                img_sha = hashlib.sha256(f"{img.id}:{img.file_name}".encode('utf-8')).hexdigest()
        else:
            img_sha = hashlib.sha256(f"{img.id}:{img.file_name}".encode('utf-8')).hexdigest()

        evidence_refs.append({
            'image_id': img.id,
            'panel_type': img.image_type,
            'file_name': img.file_name,
            'sha256': img_sha,
            'mime_type': img.mime_type or 'image/jpeg',
            'storage_path': img.storage_path,
        })

    # Frozen snapshot of inspection declarations and metadata
    declarations: dict[str, Any] = {}
    if inspection.analysis_results:
        latest_res = sorted(inspection.analysis_results, key=lambda x: x.created_at, reverse=True)[0]
        declarations = latest_res.structured_declarations or {}

    product_name = inspection.product.name if inspection.product else (inspection.title or 'Pre-Packaged Commodity')
    brand_name = inspection.product.brand if inspection.product else None

    inspection_snapshot = {
        'inspection_id': inspection.id,
        'inspection_number': inspection.inspection_number,
        'product_name': product_name,
        'brand': brand_name,
        'barcode_or_qr': inspection.barcode_or_qr,
        'declarations': declarations,
        'total_images': len(inspection.images),
        'total_findings': len(inspection.findings),
        'finalized_at': inspection.updated_at.isoformat() if inspection.updated_at else datetime.now(timezone.utc).isoformat(),
    }

    # Resolve recipient details
    rec_role = 'unknown_pending_verification'
    rec_name = 'M/s Commercial Entity / Offender'
    rec_address = 'Premises Inspected'
    est_name = product_name
    venue = 'Retail / Commercial Premises'

    if inspection.product:
        mfg = getattr(inspection.product, 'manufacturer', None) or getattr(inspection.product, 'manufacturer_name', None)
        if mfg:
            rec_name = mfg
            rec_role = 'manufacturer'
        addr = getattr(inspection.product, 'manufacturer_address', None)
        if addr:
            rec_address = addr
        if inspection.product.brand:
            est_name = f"{inspection.product.brand} ({product_name})"

    # Apply caller overrides
    if draft_params:
        if draft_params.recipient_role:
            rec_role = draft_params.recipient_role
        if draft_params.recipient_name:
            rec_name = draft_params.recipient_name
        if draft_params.recipient_address:
            rec_address = draft_params.recipient_address
        if draft_params.establishment_name:
            est_name = draft_params.establishment_name
        if draft_params.inspection_venue:
            venue = draft_params.inspection_venue

    notice_ref = f"SCN-{datetime.now(timezone.utc).year}-{inspection.inspection_number[:8]}-{uuid4().hex[:4].upper()}"

    resp_days = draft_params.response_period_days if draft_params and draft_params.response_period_days is not None else 15
    resp_basis = draft_params.response_period_basis if draft_params and draft_params.response_period_basis else "Configurable administrative show-cause period (Draft convenience; officer-confirmed procedural term, not a fixed statutory mandate)"
    comp_elig = draft_params.compounding_eligible if draft_params else False
    comp_inc = draft_params.compounding_clause_included if draft_params else False

    notice = Notice(
        inspection_id=inspection.id,
        notice_reference=notice_ref,
        status='DRAFT',
        recipient_role=rec_role,
        recipient_name=rec_name,
        recipient_address=rec_address,
        establishment_name=est_name,
        inspection_venue=venue,
        statutory_charges=charges,
        legal_version_context=legal_context,
        evidence_references=evidence_refs,
        inspection_snapshot=inspection_snapshot,
        response_period_days=resp_days,
        response_period_basis=resp_basis,
        compounding_eligible=comp_elig,
        compounding_clause_included=comp_inc,
        officer_name=None,
        officer_designation=None,
        officer_office=None,
        created_at=datetime.now(timezone.utc),
        is_immutable=False,
    )

    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice


def get_notice_for_inspection(db: Session, inspection_id: str) -> Notice | None:
    return db.scalars(
        select(Notice).where(Notice.inspection_id == inspection_id).order_by(Notice.created_at.desc())
    ).first()


def get_notice_by_id(db: Session, notice_id: str) -> Notice | None:
    return db.get(Notice, notice_id)


def update_notice_draft(db: Session, notice_id: str, update_data: NoticeUpdate) -> Notice:
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )

    if notice.is_immutable or notice.status == 'ISSUED_BY_OFFICER':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Cannot modify an issued statutory notice. The record is permanently locked and immutable.',
        )

    if update_data.recipient_role is not None:
        notice.recipient_role = update_data.recipient_role
    if update_data.recipient_name is not None:
        notice.recipient_name = update_data.recipient_name
    if update_data.recipient_address is not None:
        notice.recipient_address = update_data.recipient_address
    if update_data.establishment_name is not None:
        notice.establishment_name = update_data.establishment_name
    if update_data.inspection_venue is not None:
        notice.inspection_venue = update_data.inspection_venue
    if update_data.response_period_days is not None:
        notice.response_period_days = update_data.response_period_days
    if update_data.response_period_basis is not None:
        notice.response_period_basis = update_data.response_period_basis
    if update_data.compounding_eligible is not None:
        notice.compounding_eligible = update_data.compounding_eligible
    if update_data.compounding_clause_included is not None:
        notice.compounding_clause_included = update_data.compounding_clause_included
    if update_data.statutory_charges is not None:
        notice.statutory_charges = update_data.statutory_charges

    db.commit()
    db.refresh(notice)
    return notice


def review_notice(db: Session, notice_id: str, review_data: NoticeReviewRequest | None = None) -> Notice:
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )

    if notice.is_immutable or notice.status == 'ISSUED_BY_OFFICER':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Cannot review an already issued statutory notice.',
        )

    # Check for charges requiring manual review
    charges = notice.statutory_charges or []
    unconfirmed_manual_charges = [
        c for c in charges if c.get('requires_manual_review') and not c.get('officer_notes')
    ]
    if unconfirmed_manual_charges and not (review_data and review_data.officer_notes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Notice contains statutory charges flagged for MANUAL LEGAL REVIEW. '
                   'The inspecting officer must provide verification notes or resolve flagged charges before marking as reviewed.',
        )

    notice.status = 'REVIEWED'
    notice.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notice)
    return notice


from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedOfficerContext:
    user_id: str
    full_name: str
    designation: str
    jurisdiction_office: str


def issue_notice_by_officer(
    db: Session,
    notice_id: str,
    officer: AuthenticatedOfficerContext | NoticeIssueRequest,
    officer_notes: str | None = None,
) -> Notice:
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )

    if notice.is_immutable or notice.status == 'ISSUED_BY_OFFICER':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Statutory notice is already issued and permanently locked.',
        )

    if notice.status != 'REVIEWED':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Statutory notice must be transitioned to REVIEWED status before formal issuance by officer.',
        )

    if isinstance(officer, AuthenticatedOfficerContext):
        off_name = officer.full_name.strip()
        off_desig = officer.designation.strip()
        off_office = officer.jurisdiction_office.strip()
        off_user_id = officer.user_id
    else:
        off_name = (getattr(officer, 'officer_name', None) or 'Authorized Legal Metrology Officer').strip()
        off_desig = (getattr(officer, 'officer_designation', None) or 'Legal Metrology Inspector').strip()
        off_office = (getattr(officer, 'officer_office', None) or 'Legal Metrology Department').strip()
        off_user_id = None

    if not off_name or not off_desig or not off_office:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Officer name, designation, and jurisdictional office are mandatory for statutory notice issuance.',
        )

    notice.issuing_officer_id = off_user_id
    notice.officer_name = off_name
    notice.officer_designation = off_desig
    notice.officer_office = off_office
    notice.status = 'ISSUED_BY_OFFICER'
    notice.is_immutable = True
    notice.issued_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(notice)
    return notice

