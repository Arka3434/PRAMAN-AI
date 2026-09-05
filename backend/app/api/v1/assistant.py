"""PRAMAN Inspection Assistant API Router

Exposes deterministic, read-only assistant endpoints for inspection workflows:
- explain-finding
- summarize
- evidence-trace
- manual-review-guide

Strictly read-only; no internal ORM structures leaked; all outputs safe DTOs.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import check_inspection_ownership, require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.assistant import (
    EvidenceTraceResponse,
    FindingExplanationResponse,
    InspectionSummaryResponse,
    ManualReviewGuideResponse,
)
from app.services.assistant_service import DeterministicEvidenceAssistant

router = APIRouter(prefix="/api/v1/inspections/{inspection_id}/assistant", tags=["Assistant"])


@router.get("/explain-finding", response_model=FindingExplanationResponse)
def explain_finding(
    inspection_id: str,
    finding_id: str = Query(..., description="ID of the finding to explain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSISTANT_READ)),
) -> FindingExplanationResponse:
    """Explains an existing finding using stored evidence, rules, and notice records."""
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    assistant = DeterministicEvidenceAssistant(db)
    return assistant.explain_finding(inspection_id=inspection_id, finding_id=finding_id)


@router.get("/summarize", response_model=InspectionSummaryResponse)
def summarize_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSISTANT_READ)),
) -> InspectionSummaryResponse:
    """Summarizes an inspection deterministically based on existing stored data."""
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    assistant = DeterministicEvidenceAssistant(db)
    return assistant.summarize_inspection(inspection_id=inspection_id)


@router.get("/evidence-trace", response_model=EvidenceTraceResponse)
def trace_evidence(
    inspection_id: str,
    finding_id: str = Query(..., description="ID of the finding to trace evidence for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSISTANT_READ)),
) -> EvidenceTraceResponse:
    """Traces the optical and declaration evidence underlying an evaluation."""
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    assistant = DeterministicEvidenceAssistant(db)
    return assistant.trace_evidence(inspection_id=inspection_id, finding_id=finding_id)


@router.get("/manual-review-guide", response_model=ManualReviewGuideResponse)
def get_manual_review_guide(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ASSISTANT_READ)),
) -> ManualReviewGuideResponse:
    """Generates guidance on manual review and physical verification items."""
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    assistant = DeterministicEvidenceAssistant(db)
    return assistant.get_manual_review_guide(inspection_id=inspection_id)

