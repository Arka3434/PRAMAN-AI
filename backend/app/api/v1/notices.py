from __future__ import annotations

import io
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import check_inspection_ownership, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.notices import (
    NoticeDraftCreate,
    NoticeIssueRequest,
    NoticeRead,
    NoticeReviewRequest,
    NoticeUpdate,
)
from app.services import notice_drafting_service
from app.services.notice_drafting_service import AuthenticatedOfficerContext
from app.services.notice_pdf_generator import notice_pdf_generator

router = APIRouter(prefix='/api/v1', tags=['statutory-notices'])


@router.post(
    '/inspections/{inspection_id}/notice/draft',
    response_model=NoticeRead,
    status_code=status.HTTP_201_CREATED,
    summary='Generate a statutory notice / inspection memo draft from a finalized inspection',
)
def create_notice_draft(
    inspection_id: str,
    draft_params: NoticeDraftCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_DRAFT)),
) -> NoticeRead:
    check_inspection_ownership(inspection_id, current_user, db, require_write=True)
    notice = notice_drafting_service.draft_notice_from_inspection(db, inspection_id, draft_params)

    audit = AuditLog(
        event_type="NOTICE_DRAFTED",
        user_id=current_user.id,
        resource_type="notice",
        resource_id=notice.id,
        details={
            "notice_reference": notice.notice_reference,
            "inspection_id": notice.inspection_id,
        },
    )
    db.add(audit)
    db.commit()

    return NoticeRead.model_validate(notice)


@router.post(
    '/inspections/{inspection_id}/notices/draft',
    response_model=NoticeRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_notice_draft_alias(
    inspection_id: str,
    draft_params: NoticeDraftCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_DRAFT)),
) -> NoticeRead:
    return create_notice_draft(inspection_id, draft_params, db, current_user)


@router.get(
    '/inspections/{inspection_id}/notice',
    response_model=NoticeRead | None,
    summary='Retrieve statutory notice associated with an inspection',
)
def get_inspection_notice(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_READ)),
) -> NoticeRead | None:
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    notice = notice_drafting_service.get_notice_for_inspection(db, inspection_id)
    if not notice:
        return None
    return NoticeRead.model_validate(notice)


@router.get(
    '/inspections/{inspection_id}/notices',
    response_model=NoticeRead | None,
    include_in_schema=False,
)
def get_inspection_notice_alias(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_READ)),
) -> NoticeRead | None:
    return get_inspection_notice(inspection_id, db, current_user)


@router.get(
    '/notices/{notice_id}',
    response_model=NoticeRead,
    summary='Fetch a statutory notice by ID',
)
def get_notice(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_READ)),
) -> NoticeRead:
    notice = notice_drafting_service.get_notice_by_id(db, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )
    check_inspection_ownership(notice.inspection_id, current_user, db, require_write=False)
    return NoticeRead.model_validate(notice)


@router.put(
    '/notices/{notice_id}',
    response_model=NoticeRead,
    summary='Update draft notice fields (rejected with 409 if already issued)',
)
def update_notice(
    notice_id: str,
    payload: NoticeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_EDIT)),
) -> NoticeRead:
    notice = notice_drafting_service.get_notice_by_id(db, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )
    check_inspection_ownership(notice.inspection_id, current_user, db, require_write=True)
    updated_notice = notice_drafting_service.update_notice_draft(db, notice_id, payload)
    return NoticeRead.model_validate(updated_notice)


@router.post(
    '/notices/{notice_id}/review',
    response_model=NoticeRead,
    summary='Transition notice draft to REVIEWED status',
)
def review_notice(
    notice_id: str,
    payload: NoticeReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_REVIEW)),
) -> NoticeRead:
    notice = notice_drafting_service.get_notice_by_id(db, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )
    check_inspection_ownership(notice.inspection_id, current_user, db, require_write=True)
    reviewed_notice = notice_drafting_service.review_notice(db, notice_id, payload)

    audit = AuditLog(
        event_type="NOTICE_REVIEWED",
        user_id=current_user.id,
        resource_type="notice",
        resource_id=reviewed_notice.id,
        details={
            "notice_reference": reviewed_notice.notice_reference,
            "inspection_id": reviewed_notice.inspection_id,
        },
    )
    db.add(audit)
    db.commit()

    return NoticeRead.model_validate(reviewed_notice)


@router.post(
    '/notices/{notice_id}/issue',
    response_model=NoticeRead,
    summary='Formally issue statutory notice by officer, permanently locking the record',
)
def issue_notice(
    notice_id: str,
    payload: NoticeIssueRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_ISSUE)),
) -> NoticeRead:
    notice = notice_drafting_service.get_notice_by_id(db, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )
    check_inspection_ownership(notice.inspection_id, current_user, db, require_write=True)

    officer_name = current_user.full_name or current_user.email
    officer_designation = current_user.designation or "Legal Metrology Officer"
    officer_office = current_user.jurisdiction_office or "Department of Legal Metrology"

    officer_ctx = AuthenticatedOfficerContext(
        user_id=current_user.id,
        full_name=officer_name,
        designation=officer_designation,
        jurisdiction_office=officer_office,
    )
    notes = payload.officer_notes if payload else None
    issued_notice = notice_drafting_service.issue_notice_by_officer(
        db,
        notice_id,
        officer=officer_ctx,
        officer_notes=notes,
    )

    audit = AuditLog(
        event_type="NOTICE_ISSUED",
        user_id=current_user.id,
        resource_type="notice",
        resource_id=issued_notice.id,
        details={
            "notice_reference": issued_notice.notice_reference,
            "inspection_id": issued_notice.inspection_id,
            "officer_name": issued_notice.officer_name,
            "officer_designation": issued_notice.officer_designation,
        },
    )
    db.add(audit)
    db.commit()

    return NoticeRead.model_validate(issued_notice)


@router.get(
    '/notices/{notice_id}/pdf',
    summary='Stream the generated PDF for the notice (watermarked as DRAFT unless issued)',
)
def download_notice_pdf(
    notice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.NOTICE_READ)),
) -> StreamingResponse:
    notice = notice_drafting_service.get_notice_by_id(db, notice_id)
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Notice {notice_id} not found',
        )
    check_inspection_ownership(notice.inspection_id, current_user, db, require_write=False)

    pdf_bytes = notice_pdf_generator.generate_pdf(notice)
    filename = f"{notice.notice_reference.lower().replace('/', '_')}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(pdf_bytes)),
        },
    )

