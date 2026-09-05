import io
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import check_inspection_ownership, require_permission
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.core.storage import UPLOAD_ROOT, save_upload_file
from app.db.session import get_db
from app.models.analysis_result import AnalysisResult
from app.models.audit_log import AuditLog
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.inspection_image import InspectionImage
from app.models.product import Product
from app.models.review_decision import ReviewDecision
from app.models.user import User
from app.schemas.analysis_results import AnalysisResultRead

from app.schemas.declarations import (
    DeclarationsUpdateRequest,
    DeclarationsUpdateResponse,
)
from app.schemas.findings import FindingRead
from app.schemas.inspection_images import InspectionImageRead
from app.schemas.inspections import (
    EngineSeverityDistribution,
    EngineSummary,
    FinalResultSummary,
    InspectionComplianceSummary,
    InspectionCreate,
    InspectionHistoryItem,
    InspectionRead,
    InspectorReviewSummary,
)
from app.schemas.review_decisions import ReviewDecisionCreate, ReviewDecisionRead
from app.services.compliance_engine import (
    ComplianceEngine,
    ComplianceEvaluationReport,
    InspectionEvaluationContext,
)
from app.services.demo_validation import DemoValidationService
from app.services.ocr_service import OCRService
from app.services.quality_service import (
    assess_image_quality,
    load_quality_metadata,
    save_quality_metadata,
)
from pydantic import BaseModel, Field
from app.services.panel_fusion import (
    fuse_panel_declarations,
    FusedFieldResult,
)
from app.services.image_rotation_service import (
    create_rotated_derivative,
    get_active_image_file_path,
    load_rotation_metadata,
)
from app.services.report_generator import InspectionReportGenerator

router = APIRouter(prefix='/api/v1/inspections', tags=['inspections'])
report_generator = InspectionReportGenerator()
compliance_engine = ComplianceEngine()


class RotateImageRequest(BaseModel):
    angle: int = Field(..., description="Rotation angle in degrees clockwise: 0, 90, 180, 270")


def normalize_image_type(raw_type: str | None) -> str:
    if raw_type is None:
        return 'front'
    normalized = raw_type.strip().lower().replace(' ', '_')
    mapping = {
        'front': 'front',
        'back': 'back',
        'left_side': 'left_side',
        'left': 'left_side',
        'right_side': 'right_side',
        'right': 'right_side',
        'other': 'other',
        'primary': 'front',
    }
    return mapping.get(normalized, 'front')


@router.get('', response_model=list[InspectionHistoryItem])
async def list_inspections(
    status: str | None = Query(None, description="Filter by status (e.g. draft, review_required, completed)"),
    search: str | None = Query(None, description="Search by inspection number, title, or product name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> list[InspectionHistoryItem]:
    stmt = select(Inspection).outerjoin(Product, Inspection.product_id == Product.id)

    if status:
        stmt = stmt.where(Inspection.status.ilike(status.strip()))

    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Inspection.inspection_number.ilike(term),
                Inspection.title.ilike(term),
                Product.name.ilike(term),
            )
        )

    stmt = stmt.order_by(Inspection.created_at.desc()).limit(limit).offset(offset)
    inspections = db.scalars(stmt).all()

    items: list[InspectionHistoryItem] = []
    for insp in inspections:
        prod_name = insp.product.name if insp.product else None
        insp_name = insp.inspector.full_name if insp.inspector else None
        finding_count = len(insp.findings) if insp.findings else 0

        # Review status derived from findings and review decisions
        if finding_count == 0:
            review_status = 'COMPLETE' if insp.status == 'COMPLETED' else 'NOT_REQUIRED'
        else:
            reviewed_finding_ids = {rd.finding_id for rd in insp.review_decisions if rd.finding_id}
            reviewed_count = sum(1 for f in insp.findings if f.status == 'resolved' or f.id in reviewed_finding_ids)
            if reviewed_count == finding_count:
                review_status = 'COMPLETE'
            elif reviewed_count > 0:
                review_status = 'IN_PROGRESS'
            else:
                review_status = 'PENDING'

        # Overall result derived from structured findings and analysis
        if not insp.analysis_results:
            overall_result = 'PENDING_ANALYSIS'
        elif any(f.status == 'open' and (f.severity in ('critical', 'major') or f.rule_status == 'POTENTIAL_VIOLATION') for f in insp.findings):
            overall_result = 'POTENTIAL_VIOLATIONS_DETECTED'
        elif any(f.status == 'open' and (f.severity == 'warning' or f.rule_status in ('WARNING', 'MANUAL_REVIEW')) for f in insp.findings):
            overall_result = 'WARNINGS_OR_MANUAL_REVIEW'
        else:
            overall_result = 'COMPLIANT'

        report_available = (insp.status == 'COMPLETED')

        notice_status = None
        notice_id = None
        notice_reference = None
        if insp.notices:
            latest_notice = sorted(insp.notices, key=lambda n: n.created_at, reverse=True)[0]
            notice_status = latest_notice.status
            notice_id = latest_notice.id
            notice_reference = latest_notice.notice_reference

        items.append(
            InspectionHistoryItem(
                id=insp.id,
                inspection_number=insp.inspection_number,
                status=insp.status,
                title=insp.title,
                notes=insp.notes,
                barcode_or_qr=insp.barcode_or_qr,
                product_id=insp.product_id,
                inspector_id=insp.inspector_id,
                created_at=insp.created_at,
                updated_at=insp.updated_at,
                product_name=prod_name,
                inspector_name=insp_name,
                finding_count=finding_count,
                overall_result=overall_result,
                review_status=review_status,
                report_available=report_available,
                notice_status=notice_status,
                notice_id=notice_id,
                notice_reference=notice_reference,
            )
        )

    return items


@router.post('', response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_CREATE)),
) -> Inspection:
    if payload.product_id is not None:
        product = db.get(Product, payload.product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    # Authoritative officer identity: bind inspector_id to current_user.id where appropriate
    inspector_id = payload.inspector_id
    if current_user.role == UserRole.LEGAL_METROLOGY_INSPECTOR.value or not inspector_id:
        inspector_id = current_user.id

    if inspector_id is not None:
        inspector = db.get(User, inspector_id)
        if inspector is None:
            if inspector_id == current_user.id:
                db_user = User(
                    id=current_user.id,
                    email=current_user.email,
                    full_name=current_user.full_name,
                    role=current_user.role,
                    designation=current_user.designation,
                    jurisdiction_office=current_user.jurisdiction_office,
                    is_active=True,
                )
                db.add(db_user)
                db.flush()
                inspector = db_user
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Inspector not found')

    data = payload.model_dump()
    data['inspector_id'] = inspector_id
    inspection = Inspection(**data)
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    audit = AuditLog(
        event_type="INSPECTION_CREATED",
        user_id=current_user.id,
        resource_type="inspection",
        resource_id=inspection.id,
        details={"inspection_number": inspection.inspection_number, "product_id": inspection.product_id},
    )
    db.add(audit)
    db.commit()

    return inspection


@router.get('/{inspection_id}', response_model=InspectionRead)
async def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> Inspection:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    return inspection



@router.post('/{inspection_id}/upload-image', response_model=InspectionImageRead, status_code=status.HTTP_201_CREATED)
async def upload_inspection_image(
    inspection_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> InspectionImage:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    if file.filename is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='A file name is required.')

    saved_path, relative_path = save_upload_file(file, inspection_id)
    quality_report = assess_image_quality(saved_path)
    save_quality_metadata(saved_path, quality_report)

    image = InspectionImage(
        inspection_id=inspection_id,
        image_type='front',
        file_name=file.filename,
        storage_path=relative_path,
        mime_type=file.content_type,
        width=quality_report.width or 1200,
        height=quality_report.height or 1200,
    )
    db.add(image)
    inspection.status = 'DRAFT'
    db.commit()
    db.refresh(image)
    image.quality_assessment = quality_report
    return image


@router.post('/{inspection_id}/upload-images', response_model=list[InspectionImageRead], status_code=status.HTTP_201_CREATED)
async def upload_inspection_images(
    inspection_id: str,
    files: list[UploadFile] = File(...),
    image_type: str = Form('front'),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> list[InspectionImage]:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='At least one image is required for upload.')

    normalized_type = normalize_image_type(image_type)
    created_images: list[InspectionImage] = []
    quality_map = {}
    for file in files:
        if file.filename is None:
            continue
        saved_path, relative_path = save_upload_file(file, inspection_id)
        quality_report = assess_image_quality(saved_path)
        save_quality_metadata(saved_path, quality_report)

        image = InspectionImage(
            inspection_id=inspection_id,
            image_type=normalized_type,
            file_name=file.filename,
            storage_path=relative_path,
            mime_type=file.content_type,
            width=quality_report.width or 1200,
            height=quality_report.height or 1200,
        )
        db.add(image)
        created_images.append(image)
        quality_map[file.filename] = quality_report

    inspection.status = 'DRAFT'
    db.commit()
    for image in created_images:
        db.refresh(image)
        if image.storage_path:
            full_path = Path(__file__).resolve().parents[2] / image.storage_path
            image.quality_assessment = load_quality_metadata(full_path) or quality_map.get(image.file_name)
            image.rotation_metadata = load_rotation_metadata(full_path)
    return created_images


@router.patch('/{inspection_id}/barcode', response_model=InspectionRead)
async def update_inspection_barcode(
    inspection_id: str,
    barcode_or_qr: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> Inspection:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    if barcode_or_qr is not None:
        inspection.barcode_or_qr = barcode_or_qr.strip() or None
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get('/{inspection_id}/images', response_model=list[InspectionImageRead])
async def list_inspection_images(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> list[InspectionImage]:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    images = db.scalars(select(InspectionImage).where(InspectionImage.inspection_id == inspection_id).order_by(InspectionImage.created_at.asc())).all()
    for image in images:
        if image.storage_path:
            full_path = Path(__file__).resolve().parents[2] / image.storage_path
            active_path, _ = get_active_image_file_path(full_path)
            report = load_quality_metadata(active_path)
            if not report and active_path.exists():
                report = assess_image_quality(active_path)
                save_quality_metadata(active_path, report)
            image.quality_assessment = report
            image.rotation_metadata = load_rotation_metadata(full_path)
    return images


@router.get('/{inspection_id}/images/{image_id}/file')
async def get_inspection_image_file(
    inspection_id: str,
    image_id: str,
    original: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> FileResponse:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    image = db.get(InspectionImage, image_id)
    if image is None or image.inspection_id != inspection_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Inspection image not found')
    if not image.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Image file path not set')

    full_path = Path(__file__).resolve().parents[2] / image.storage_path
    if not full_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Image file not found on disk')

    if not original:
        active_path, _ = get_active_image_file_path(full_path)
        if active_path.exists():
            media_type = 'image/jpeg' if active_path.suffix.lower() in ('.jpg', '.jpeg') else (image.mime_type or 'image/png')
            return FileResponse(active_path, media_type=media_type)

    return FileResponse(full_path, media_type=image.mime_type or 'image/png')


@router.patch('/{inspection_id}/images/{image_id}/rotate', response_model=InspectionImageRead)
async def rotate_inspection_image(
    inspection_id: str,
    image_id: str,
    payload: RotateImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> InspectionImage:
    """
    Rotates a package panel image representation non-destructively.
    CRITICAL STATUTORY INVARIANT: The original uploaded evidence file at storage_path
    remains strictly immutable. A rotated derivative is created for preview and OCR,
    with original SHA-256 and rotation history preserved in a sidecar metadata file.
    """
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)
    image = db.get(InspectionImage, image_id)
    if image is None or image.inspection_id != inspection_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Inspection image not found')
    if not image.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Image file path not set')

    full_path = Path(__file__).resolve().parents[2] / image.storage_path
    if not full_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Original image file not found on disk')

    active_path, meta = create_rotated_derivative(full_path, payload.angle)

    quality_rep = assess_image_quality(active_path)
    save_quality_metadata(active_path, quality_rep)

    image.quality_assessment = quality_rep
    image.rotation_metadata = meta
    return image


@router.post('/{inspection_id}/analyze', response_model=AnalysisResultRead, status_code=status.HTTP_201_CREATED)
async def run_demo_analysis(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> AnalysisResult:
    """
    Multi-Panel Package Compliance Analysis (Phase 12).
    Iterates across all uploaded packaging panels (PDP / Front, Information Panels / Back, Side),
    runs OCR and per-image quality diagnostics on active representations, fuses declarations
    into a unified package profile, routes material cross-panel conflicts to MANUAL_REVIEW,
    and attributes findings directly to their source panel images.
    """
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)


    images = db.scalars(
        select(InspectionImage)
        .where(InspectionImage.inspection_id == inspection_id)
        .order_by(InspectionImage.created_at.asc())
    ).all()
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='An uploaded image is required before analysis can run.')

    per_image_results = []
    quality_reports = {}
    aggregated_ocr_text_parts = []
    all_ocr_regions = []
    total_confidence = 0.0

    for img in images:
        if not img.storage_path:
            continue
        orig_path = Path(__file__).resolve().parents[2] / img.storage_path
        if not orig_path.exists():
            continue

        active_path, _ = get_active_image_file_path(orig_path)

        # Per-image quality diagnostics
        q = load_quality_metadata(active_path)
        if not q and active_path.exists():
            q = assess_image_quality(active_path)
            save_quality_metadata(active_path, q)
        if q:
            quality_reports[img.id] = q.model_dump()

        # Run OCR on active panel representation
        ocr_result = OCRService.analyze_image(active_path, inspection_id)
        per_image_results.append({
            'image_id': img.id,
            'image_type': img.image_type or 'other',
            'file_name': img.file_name,
            'storage_path': img.storage_path,
            'active_path': str(active_path),
            'structured_declarations': ocr_result.get('structured_declarations', {}),
            'ocr_confidence': ocr_result.get('ocr_confidence', 0.0),
            'ocr_text': ocr_result.get('ocr_text', ''),
            'ocr_regions': ocr_result.get('ocr_regions', []),
            'extraction_metadata': ocr_result.get('extraction_metadata', {}),
        })

        panel_label = (img.image_type or 'PANEL').upper()
        if ocr_result.get('ocr_text'):
            aggregated_ocr_text_parts.append(f"--- PANEL: {panel_label} ({img.file_name}) ---\n{ocr_result['ocr_text']}")
        all_ocr_regions.extend(ocr_result.get('ocr_regions', []))
        total_confidence += ocr_result.get('confidence', 0.0)

    if not per_image_results:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded image files are missing from local storage.')

    # Execute Multi-Panel Declaration Fusion
    fused_declarations, fused_results = fuse_panel_declarations(per_image_results)
    fused_declarations['inspection_id'] = inspection_id

    overall_confidence = total_confidence / len(per_image_results) if per_image_results else 0.0

    first_meta = per_image_results[0].get('extraction_metadata', {}) if per_image_results else {}
    current_meta = dict(first_meta)
    current_meta.update({
        'pipeline': 'MultiPanelFusion',
        'per_image_ocr': per_image_results,
        'image_quality': quality_reports,
        'raw_ocr_declarations': dict(fused_declarations),
        'panel_conflicts': {
            k: res.model_dump()
            for k, res in fused_results.items()
            if res.has_conflict
        },
        'fused_provenance': {
            k: {
                'primary_image_id': res.primary_image_id,
                'primary_image_type': res.primary_image_type,
                'primary_storage_path': res.primary_storage_path,
                'routing': res.routing,
                'has_conflict': res.has_conflict,
            }
            for k, res in fused_results.items()
        }
    })

    aggregated_ocr_text = '\n\n'.join(aggregated_ocr_text_parts)

    analysis = AnalysisResult(
        inspection_id=inspection_id,
        status='completed',
        confidence=overall_confidence,
        structured_declarations=fused_declarations,
        ocr_text=aggregated_ocr_text,
        ocr_confidence=overall_confidence,
        ocr_regions=all_ocr_regions,
        extraction_metadata=current_meta,
    )
    db.add(analysis)
    db.flush()

    primary_image_record = images[0]
    _evaluate_and_sync_findings(db, inspection, analysis, primary_image_record, fused_results=fused_results)

    db.commit()
    db.refresh(analysis)
    return analysis


def _evaluate_and_sync_findings(
    db: Session,
    inspection: Inspection,
    analysis: AnalysisResult,
    image_record: InspectionImage | None = None,
    fused_results: dict[str, FusedFieldResult] | None = None,
) -> ComplianceEvaluationReport:
    """
    Evaluates compliance using the deterministic ComplianceEngine against structured declarations
    and synchronizes findings safely while preserving inspector review history and attributing
    evidence to specific source panels.
    """
    notes_text = (inspection.notes or '').lower()
    title_text = (inspection.title or '').lower()
    ocr_text = (analysis.ocr_text or '').lower()

    is_imported = None
    if any(term in notes_text or term in title_text for term in ['imported', 'import']):
        is_imported = True
    elif 'imported by' in ocr_text or 'country of origin' in ocr_text:
        is_imported = True
    elif 'domestic' in notes_text or 'domestic' in title_text:
        is_imported = False

    product_category = 'general'
    if inspection.product and inspection.product.category:
        product_category = inspection.product.category

    inspection_date_str = (
        inspection.created_at.date().isoformat()
        if inspection.created_at
        else datetime.now(timezone.utc).date().isoformat()
    )

    evaluation_context = InspectionEvaluationContext(
        inspection_id=inspection.id,
        inspection_date=inspection_date_str,
        inspection_context={
            'is_imported': is_imported,
            'commodity_category': product_category,
            'consumer_type': 'retail',
            'inspection_date': inspection_date_str,
            'created_at': inspection.created_at.isoformat() if inspection.created_at else None,
        },
        structured_declarations=analysis.structured_declarations or {},
        ocr_evidence={
            'ocr_text': analysis.ocr_text or '',
            'ocr_confidence': analysis.ocr_confidence or 0.0,
            'ocr_regions': analysis.ocr_regions or [],
            'source_file': image_record.file_name or (Path(image_record.storage_path).name if image_record and image_record.storage_path else None) if image_record else None,
        },
    )

    evaluation_report = compliance_engine.evaluate(evaluation_context)

    current_meta = dict(analysis.extraction_metadata or {})
    current_meta['catalog_version'] = evaluation_report.catalog_version
    current_meta['catalog_hash'] = evaluation_report.catalog_hash
    current_meta['inspection_date'] = evaluation_report.inspection_date
    current_meta['engine_summary'] = evaluation_report.summary
    analysis.extraction_metadata = current_meta

    panel_conflicts = current_meta.get('panel_conflicts', {})
    fused_provenance = current_meta.get('fused_provenance', {})
    inspector_corrections = current_meta.get('inspector_corrections', [])
    corrected_field_names = {c.get('field_name') for c in inspector_corrections if c.get('field_name')}

    # Idempotency: remove stale findings
    existing_findings = db.scalars(
        select(Finding).where(Finding.inspection_id == inspection.id)
    ).all()
    for f in existing_findings:
        db.delete(f)
    db.flush()

    rule_field_map = {
        'PCR-001': 'manufacturer_name',
        'PCR-002': 'country_of_origin',
        'PCR-003': 'commodity_name',
        'PCR-004': 'net_quantity',
        'PCR-005': 'month_year',
        'PCR-006': 'retail_sale_price',
        'PCR-007': 'consumer_contact',
        'PCR-2011-R06-01': 'manufacturer_name',
        'PCR-2011-R06-02': 'country_of_origin',
        'PCR-2011-R06-03': 'commodity_name',
        'PCR-2011-R06-04': 'net_quantity',
        'PCR-2011-R06-05': 'month_year',
        'PCR-2011-R06-06': 'retail_sale_price',
        'PCR-2011-R06-07': 'consumer_contact',
    }

    new_findings = evaluation_report.to_findings_projection()

    for item in new_findings:
        rule_id = item.get('rule_check_id')
        ev_ref = item.get('evidence_reference')
        ev_dict = {}
        if ev_ref:
            try:
                ev_dict = json.loads(ev_ref)
                if not isinstance(ev_dict, dict):
                    ev_dict = {}
            except Exception:
                ev_dict = {}

        # Resolve field mapping and check for conflicts
        conflicting_field = None
        if rule_id in ('PCR-001', 'PCR-2011-R06-01'):
            for sub in ('manufacturer_name', 'manufacturer_address'):
                if sub not in corrected_field_names:
                    if fused_results and sub in fused_results and fused_results[sub].has_conflict:
                        conflicting_field = sub
                        break
                    elif panel_conflicts and sub in panel_conflicts:
                        conflicting_field = sub
                        break
        else:
            mapped_f = rule_field_map.get(rule_id)
            if mapped_f and mapped_f not in corrected_field_names:
                if fused_results and mapped_f in fused_results and fused_results[mapped_f].has_conflict:
                    conflicting_field = mapped_f
                elif panel_conflicts and mapped_f in panel_conflicts:
                    conflicting_field = mapped_f

        # Resolve panel-specific provenance
        target_image_id = None
        target_storage_path = None
        target_panel_type = None

        lookup_field = conflicting_field or rule_field_map.get(rule_id)
        if lookup_field:
            if fused_results and lookup_field in fused_results:
                target_image_id = fused_results[lookup_field].primary_image_id
                target_storage_path = fused_results[lookup_field].primary_storage_path
                target_panel_type = fused_results[lookup_field].primary_image_type
            elif fused_provenance and lookup_field in fused_provenance:
                target_image_id = fused_provenance[lookup_field].get('primary_image_id')
                target_storage_path = fused_provenance[lookup_field].get('primary_storage_path')
                target_panel_type = fused_provenance[lookup_field].get('primary_image_type')

        if not target_image_id and image_record:
            target_image_id = image_record.id
            target_storage_path = image_record.storage_path
            target_panel_type = image_record.image_type

        if target_image_id:
            ev_dict['image_id'] = target_image_id
        if target_storage_path:
            ev_dict['storage_path'] = target_storage_path.replace('\\', '/')
        if target_panel_type:
            ev_dict['panel_type'] = target_panel_type

        # STATUTORY INTEGRITY INVARIANT:
        # If a material cross-panel conflict exists, deterministically route to MANUAL_REVIEW.
        # OCR confidence alone must NEVER establish legal truth or pick a winner.
        if conflicting_field:
            item_severity = 'warning'
            item_status = 'open'
            item_title = f"{rule_id}: Conflicting declarations across packaging panels"
            if fused_results and conflicting_field in fused_results:
                item_description = fused_results[conflicting_field].conflict_description
                ev_dict['conflict_candidates'] = [c.model_dump() for c in fused_results[conflicting_field].candidates]
            else:
                c_data = panel_conflicts.get(conflicting_field, {})
                item_description = c_data.get('conflict_description', 'Conflicting declarations detected across package panels. Manual inspector review is legally mandatory.')
                ev_dict['conflict_candidates'] = c_data.get('candidates', [])

            ev_dict['has_conflict'] = True
            ev_dict['rule_status'] = 'MANUAL_REVIEW'
        else:
            item_severity = item['severity']
            item_status = item['status']
            item_title = item['title']
            item_description = item['description']

        ev_ref = json.dumps(ev_dict)

        finding = Finding(
            inspection_id=inspection.id,
            severity=item_severity,
            status=item_status,
            title=item_title,
            description=item_description,
            detected_value=item['detected_value'],
            rule_check_id=item['rule_check_id'],
            evidence_reference=ev_ref,
        )
        db.add(finding)

    inspection.status = 'REVIEW_REQUIRED'
    return evaluation_report


@router.get('/{inspection_id}/analysis', response_model=AnalysisResultRead | None)
async def get_analysis_result(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> AnalysisResult | None:
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    result = db.scalars(select(AnalysisResult).where(AnalysisResult.inspection_id == inspection_id).order_by(AnalysisResult.created_at.desc())).first()
    return result


@router.patch('/{inspection_id}/declarations', response_model=DeclarationsUpdateResponse)
async def update_inspection_declarations(
    inspection_id: str,
    payload: DeclarationsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DECLARATION_CORRECT)),
) -> DeclarationsUpdateResponse:
    """
    Inspector declaration review and field correction (Phase 9).
    Allows an inspector to review and correct structured declarations, recording
    audit metadata ('Inspector Verified', timestamp, old/new values), and explicitly
    re-running the deterministic ComplianceEngine against the updated declarations.
    Raw OCR evidence (text, regions, confidence, source image) is strictly immutable.
    """
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    analysis = db.scalars(
        select(AnalysisResult)
        .where(AnalysisResult.inspection_id == inspection_id)
        .order_by(AnalysisResult.created_at.desc())
    ).first()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot update declarations: Inspection analysis has not been performed yet.',
        )

    current_meta = dict(analysis.extraction_metadata or {})
    # Invariant: Raw machine-extracted declarations must be preserved
    if 'raw_ocr_declarations' not in current_meta:
        current_meta['raw_ocr_declarations'] = dict(analysis.structured_declarations or {})
    raw_ocr_decls = current_meta['raw_ocr_declarations']

    corrections_audit = list(current_meta.get('inspector_corrections') or [])
    old_decls = dict(analysis.structured_declarations or {})
    updated_decls = dict(old_decls)

    # Support structured declaration fields without destructive normalization
    for field_name, new_val in payload.declarations.items():
        old_val = old_decls.get(field_name)
        if old_val != new_val:
            corrections_audit.append({
                'field_name': field_name,
                'original_value': old_val,
                'corrected_value': new_val,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'notes': payload.notes,
                'status': 'Inspector Verified',
                'officer_id': current_user.id,
                'officer_name': current_user.full_name or current_user.email,
            })
            updated_decls[field_name] = new_val

    analysis.structured_declarations = updated_decls
    current_meta['inspector_corrections'] = corrections_audit
    analysis.extraction_metadata = current_meta

    image_record = db.scalars(
        select(InspectionImage)
        .where(InspectionImage.inspection_id == inspection_id)
        .order_by(InspectionImage.created_at.asc())
    ).first()

    _evaluate_and_sync_findings(db, inspection, analysis, image_record)

    audit = AuditLog(
        event_type="DECLARATION_CORRECTED",
        user_id=current_user.id,
        resource_type="inspection",
        resource_id=inspection_id,
        details={"fields": list(payload.declarations.keys()), "notes": payload.notes},
    )
    db.add(audit)

    db.commit()
    db.refresh(analysis)

    compliance_summary = await get_inspection_compliance_summary(inspection_id=inspection_id, db=db, current_user=current_user)

    return DeclarationsUpdateResponse(
        inspection_id=inspection_id,
        structured_declarations=analysis.structured_declarations or {},
        raw_ocr_declarations=raw_ocr_decls,
        inspector_corrections=corrections_audit,
        compliance_summary=compliance_summary,
        analysis=analysis,
    )


@router.get('/{inspection_id}/declarations', response_model=DeclarationsUpdateResponse)
async def get_inspection_declarations(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> DeclarationsUpdateResponse:
    """Retrieves current structured declarations, raw OCR baseline, and inspector correction audit history."""
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)

    analysis = db.scalars(
        select(AnalysisResult)
        .where(AnalysisResult.inspection_id == inspection_id)
        .order_by(AnalysisResult.created_at.desc())
    ).first()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Declarations not available: inspection analysis has not been performed',
        )

    current_meta = dict(analysis.extraction_metadata or {})
    raw_ocr_decls = current_meta.get('raw_ocr_declarations') or dict(analysis.structured_declarations or {})
    corrections_audit = list(current_meta.get('inspector_corrections') or [])
    compliance_summary = await get_inspection_compliance_summary(inspection_id=inspection_id, db=db, current_user=current_user)

    return DeclarationsUpdateResponse(
        inspection_id=inspection_id,
        structured_declarations=analysis.structured_declarations or {},
        raw_ocr_declarations=raw_ocr_decls,
        inspector_corrections=corrections_audit,
        compliance_summary=compliance_summary,
        analysis=analysis,
    )


@router.get('/{inspection_id}/findings', response_model=list[FindingRead])
async def list_findings(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> list[Finding]:
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)
    findings = db.scalars(select(Finding).where(Finding.inspection_id == inspection_id).order_by(Finding.created_at.desc())).all()
    return findings


@router.post('/{inspection_id}/review', response_model=ReviewDecisionRead, status_code=status.HTTP_201_CREATED)
async def submit_review(
    inspection_id: str,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FINDING_REVIEW)),
) -> ReviewDecision:
    check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    if payload.decision not in {'confirm', 'reject', 'manual_review'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Decision must be one of: confirm, reject, manual_review')

    if payload.finding_id:
        finding = db.get(Finding, payload.finding_id)
        if finding is None or finding.inspection_id != inspection_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Finding not found for this inspection')
        notes_payload = json.dumps({'finding_id': payload.finding_id, 'notes': payload.notes})
    else:
        notes_payload = payload.notes

    if db.get(User, current_user.id) is None:
        db.add(User(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            designation=current_user.designation,
            jurisdiction_office=current_user.jurisdiction_office,
            is_active=True,
        ))
        db.flush()

    decision = ReviewDecision(
        inspection_id=inspection_id,
        decision=payload.decision,
        reviewer_id=current_user.id,
        reviewer_name=payload.reviewer_name or current_user.full_name or current_user.email,
        notes=notes_payload,
    )
    db.add(decision)

    audit = AuditLog(
        event_type="FINDING_REVIEWED",
        user_id=current_user.id,
        resource_type="inspection",
        resource_id=inspection_id,
        details={
            "finding_id": payload.finding_id,
            "decision": payload.decision,
        },
    )
    db.add(audit)

    db.commit()
    db.refresh(decision)
    return decision


@router.post('/{inspection_id}/findings/{finding_id}/review', response_model=ReviewDecisionRead, status_code=status.HTTP_201_CREATED)
async def submit_finding_review(
    inspection_id: str,
    finding_id: str,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.FINDING_REVIEW)),
) -> ReviewDecision:
    check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    finding = db.get(Finding, finding_id)
    if finding is None or finding.inspection_id != inspection_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Finding not found for this inspection')

    if payload.decision not in {'confirm', 'reject', 'manual_review'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Decision must be one of: confirm, reject, manual_review')

    notes_payload = json.dumps({'finding_id': finding_id, 'notes': payload.notes})
    if db.get(User, current_user.id) is None:
        db.add(User(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            designation=current_user.designation,
            jurisdiction_office=current_user.jurisdiction_office,
            is_active=True,
        ))
        db.flush()

    decision = ReviewDecision(
        inspection_id=inspection_id,
        decision=payload.decision,
        reviewer_id=current_user.id,
        reviewer_name=payload.reviewer_name or current_user.full_name or current_user.email,
        notes=notes_payload,
    )
    db.add(decision)

    audit = AuditLog(
        event_type="FINDING_REVIEWED",
        user_id=current_user.id,
        resource_type="inspection",
        resource_id=inspection_id,
        details={
            "finding_id": finding_id,
            "decision": payload.decision,
        },
    )
    db.add(audit)

    db.commit()
    db.refresh(decision)
    return decision


@router.get('/{inspection_id}/reviews', response_model=list[ReviewDecisionRead])
async def list_reviews(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> list[ReviewDecision]:
    check_inspection_ownership(inspection_id, current_user, db, require_write=False)

    reviews = db.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.inspection_id == inspection_id)
        .order_by(ReviewDecision.created_at.desc())
    ).all()
    return reviews


@router.post('/{inspection_id}/finalize', response_model=InspectionRead)
async def finalize_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_FINALIZE)),
) -> Inspection:
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=True)

    findings = db.scalars(
        select(Finding).where(Finding.inspection_id == inspection_id)
    ).all()

    unreviewed = [f for f in findings if f.inspector_decision is None]
    if unreviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot finalize inspection: {len(unreviewed)} finding(s) have not been reviewed by an inspector.',
        )

    manual_reviews = [f for f in findings if f.inspector_decision == 'manual_review']
    if manual_reviews:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot finalize inspection: {len(manual_reviews)} finding(s) require manual review resolution.',
        )

    if not findings and inspection.status == 'REVIEW_REQUIRED' and not inspection.review_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot finalize inspection: inspector review must be completed before finalization.',
        )

    inspection.status = 'COMPLETED'

    audit = AuditLog(
        event_type="INSPECTION_FINALIZED",
        user_id=current_user.id,
        resource_type="inspection",
        resource_id=inspection.id,
        details={"inspection_number": inspection.inspection_number},
    )
    db.add(audit)

    db.commit()
    db.refresh(inspection)
    return inspection


@router.get('/{inspection_id}/summary', response_model=InspectionComplianceSummary)
async def get_inspection_compliance_summary(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(require_permission(Permission.INSPECTION_READ)),
) -> InspectionComplianceSummary:
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Inspection not found')

    if current_user is not None:
        check_inspection_ownership(inspection_id, current_user, db, require_write=False)

    findings = db.scalars(
        select(Finding).where(Finding.inspection_id == inspection_id).order_by(Finding.created_at.asc())
    ).all()

    analysis = db.scalars(
        select(AnalysisResult)
        .where(AnalysisResult.inspection_id == inspection_id)
        .order_by(AnalysisResult.created_at.desc())
    ).first()

    meta = analysis.extraction_metadata if analysis and analysis.extraction_metadata else {}
    catalog_version = meta.get('catalog_version') or compliance_engine.catalog_version
    catalog_hash = meta.get('catalog_hash') or compliance_engine.catalog_hash
    inspection_date = meta.get('inspection_date') or (
        inspection.created_at.date().isoformat() if inspection.created_at else None
    )
    meta_engine_summary = meta.get('engine_summary') if isinstance(meta.get('engine_summary'), dict) else None

    total_checks = len(findings)

    # Derive status counts strictly from structured fields (status, severity, rule_status, rule_check_id)
    passed_count = sum(
        1
        for f in findings
        if f.status == 'resolved' or f.severity == 'pass' or getattr(f, 'rule_status', None) == 'PASS'
    )
    violations_count = sum(
        1
        for f in findings
        if f.status != 'resolved'
        and (f.severity in {'critical', 'major'} or getattr(f, 'rule_status', None) == 'POTENTIAL_VIOLATION')
    )
    manual_review_count = sum(
        1
        for f in findings
        if f.status != 'resolved'
        and (getattr(f, 'rule_status', None) == 'MANUAL_REVIEW' or f.rule_check_id in {'PCR-006', 'PCR-008'})
    )
    warnings_count = sum(
        1
        for f in findings
        if f.status != 'resolved'
        and f.severity == 'warning'
        and getattr(f, 'rule_status', None) != 'MANUAL_REVIEW'
        and f.rule_check_id not in {'PCR-006', 'PCR-008'}
    )

    not_applicable_count = int(meta_engine_summary.get('not_applicable', 0)) if meta_engine_summary else 0

    crit_count = sum(1 for f in findings if f.severity == 'critical')
    major_count = sum(1 for f in findings if f.severity == 'major')
    warn_count = sum(1 for f in findings if f.severity == 'warning')
    pass_sev_count = sum(1 for f in findings if f.severity == 'pass')

    # Overall engine result derived purely from structured findings / analysis presence
    if analysis is None and total_checks == 0:
        overall_engine_result = 'PENDING_ANALYSIS'
    elif violations_count > 0:
        overall_engine_result = 'POTENTIAL_VIOLATIONS_DETECTED'
    elif warnings_count > 0 or manual_review_count > 0:
        overall_engine_result = 'WARNINGS_OR_MANUAL_REVIEW'
    else:
        # Zero violations and zero warnings/manual-review (e.g. all evaluated checks pass or are not applicable)
        overall_engine_result = 'COMPLIANT'

    reviewed_count = sum(1 for f in findings if f.inspector_decision is not None)
    pending_count = sum(1 for f in findings if f.inspector_decision is None)
    confirmed_count = sum(1 for f in findings if f.inspector_decision == 'confirm')
    rejected_count = sum(1 for f in findings if f.inspector_decision == 'reject')
    insp_manual_count = sum(1 for f in findings if f.inspector_decision == 'manual_review')

    if total_checks == 0:
        review_status = 'COMPLETE' if inspection.review_decisions else 'NOT_STARTED'
    elif reviewed_count == 0:
        review_status = 'PENDING'
    elif pending_count == 0 and insp_manual_count == 0:
        review_status = 'COMPLETE'
    else:
        review_status = 'IN_PROGRESS'

    # Guardrails: Unreviewed findings or unresolved manual reviews block finalization;
    # zero-finding packages are not blocked merely for having 0 findings.
    blocking_reasons: list[str] = []
    if pending_count > 0:
        blocking_reasons.append(f'{pending_count} finding(s) have not been reviewed by an inspector.')
    if insp_manual_count > 0:
        blocking_reasons.append(f'{insp_manual_count} finding(s) require manual review resolution.')
    if not findings and inspection.status == 'REVIEW_REQUIRED' and not inspection.review_decisions:
        blocking_reasons.append('Inspector review must be completed before finalization.')
    if not findings and analysis is None and not inspection.review_decisions:
        blocking_reasons.append('Inspection must be analyzed or reviewed before finalization.')

    can_finalize = len(blocking_reasons) == 0

    return InspectionComplianceSummary(
        inspection_id=inspection_id,
        inspection_status=inspection.status,
        inspection_date=inspection_date,
        catalog_version=catalog_version,
        catalog_hash=catalog_hash,
        engine_summary=EngineSummary(
            overall_result=overall_engine_result,
            total_checks=total_checks,
            passed=passed_count,
            potential_violations=violations_count,
            warnings=warnings_count,
            manual_review=manual_review_count,
            not_applicable=not_applicable_count,
            severity_distribution=EngineSeverityDistribution(
                critical=crit_count,
                major=major_count,
                warning=warn_count,
                pass_count=pass_sev_count,
            ),
        ),
        inspector_summary=InspectorReviewSummary(
            total_findings=total_checks,
            reviewed_count=reviewed_count,
            pending_count=pending_count,
            confirmed_count=confirmed_count,
            rejected_count=rejected_count,
            manual_review_count=insp_manual_count,
            review_status=review_status,
        ),
        final_result=FinalResultSummary(
            can_finalize=can_finalize,
            inspection_status=inspection.status,
            blocking_reasons=blocking_reasons,
        ),
    )


@router.get('/{inspection_id}/report')
async def generate_inspection_report(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EXPORT)),
) -> StreamingResponse:
    """Generates an evidence-backed PDF inspection report under statutory guardrails."""
    inspection = check_inspection_ownership(inspection_id, current_user, db, require_write=False)

    findings = db.scalars(
        select(Finding).where(Finding.inspection_id == inspection_id).order_by(Finding.created_at.asc())
    ).all()

    summary = await get_inspection_compliance_summary(inspection_id=inspection_id, db=db, current_user=current_user)

    # Finalization guardrail enforcement:
    # An inspection must be finalized (COMPLETED) or satisfy finalization guardrails to be reportable.
    if inspection.status != 'COMPLETED' and not summary.final_result.can_finalize:
        reasons = "; ".join(summary.final_result.blocking_reasons)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot generate final report: inspection is not eligible ({reasons})',
        )

    pdf_bytes = report_generator.generate_pdf(
        inspection=inspection,
        findings=findings,
        summary=summary.model_dump(),
        storage_base_path=UPLOAD_ROOT.parent,  # absolute path — invariant regardless of working directory
    )

    filename = f"praman_inspection_report_{inspection.inspection_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(pdf_bytes)),
        },
    )


