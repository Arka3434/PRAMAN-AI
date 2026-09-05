from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.user import User
from app.schemas.products import (
    ProductCreate,
    ProductDetailResponse,
    ProductInspectionRecord,
    ProductRead,
    ProductSummary,
    ProductUpdate,
)

router = APIRouter(prefix='/api/v1/products', tags=['products'])



def compute_product_metrics(product: Product) -> dict:
    """
    Computes summary metrics for a product across all associated inspections.
    Preserves Phase 7 scoring invariants:
    - Compliance score = passed rule checks / evaluated checks (excluding NOT_APPLICABLE).
    - latest_verdict derives strictly from the latest inspection's statutory evaluation state.
    """
    sorted_inspections = sorted(
        product.inspections or [],
        key=lambda i: (i.created_at or datetime.min.replace(tzinfo=timezone.utc), i.inspection_number or ''),
        reverse=True,
    )
    inspection_count = len(sorted_inspections)
    last_inspected_at = sorted_inspections[0].created_at if sorted_inspections else None

    # Calculate compliance score across all evaluated checks for this product
    all_findings: list[Finding] = []
    for insp in sorted_inspections:
        if insp.findings:
            all_findings.extend(insp.findings)

    evaluated = [
        f for f in all_findings
        if f.rule_status in {'PASS', 'POTENTIAL_VIOLATION', 'WARNING', 'MANUAL_REVIEW'}
    ]
    if evaluated:
        passed = sum(1 for f in evaluated if f.rule_status == 'PASS')
        compliance_score = round((passed / len(evaluated)) * 100.0, 1)
    else:
        compliance_score = None

    # Derive latest_verdict strictly from the most recent inspection's statutory findings
    if not sorted_inspections:
        latest_verdict = 'NO_INSPECTIONS'
    else:
        latest_insp = sorted_inspections[0]
        findings = latest_insp.findings or []
        if not latest_insp.analysis_results:
            latest_verdict = 'PENDING_ANALYSIS'
        elif any(
            f.rule_status == 'POTENTIAL_VIOLATION'
            or (f.severity in ('critical', 'major') and f.rule_status != 'PASS')
            for f in findings
        ):
            latest_verdict = 'POTENTIAL_VIOLATION'
        elif any(
            f.rule_status in ('WARNING', 'MANUAL_REVIEW') or f.severity == 'warning'
            for f in findings
        ):
            latest_verdict = 'WARNINGS_OR_MANUAL_REVIEW'
        elif any(f.rule_status == 'PASS' for f in findings):
            latest_verdict = 'COMPLIANT'
        else:
            latest_verdict = 'PENDING_ANALYSIS'

    return {
        'inspection_count': inspection_count,
        'last_inspected_at': last_inspected_at,
        'compliance_score': compliance_score,
        'latest_verdict': latest_verdict,
    }


def compute_inspection_record(insp: Inspection) -> ProductInspectionRecord:
    findings = insp.findings or []
    if not insp.analysis_results:
        overall_result = 'PENDING_ANALYSIS'
    elif any(
        f.rule_status == 'POTENTIAL_VIOLATION'
        or (f.severity in ('critical', 'major') and f.rule_status != 'PASS')
        for f in findings
    ):
        overall_result = 'POTENTIAL_VIOLATIONS_DETECTED'
    elif any(
        f.rule_status in ('WARNING', 'MANUAL_REVIEW') or f.severity == 'warning'
        for f in findings
    ):
        overall_result = 'WARNINGS_OR_MANUAL_REVIEW'
    elif any(f.rule_status == 'PASS' for f in findings):
        overall_result = 'COMPLIANT'
    else:
        overall_result = 'PENDING_ANALYSIS'

    return ProductInspectionRecord(
        id=insp.id,
        inspection_number=insp.inspection_number,
        status=insp.status,
        created_at=insp.created_at,
        overall_result=overall_result,
        finding_count=len(findings),
        report_available=(insp.status == 'COMPLETED'),
    )


@router.get('', response_model=list[ProductSummary])
def list_products(
    search: str | None = Query(default=None, description='Search by product name, brand, or manufacturer'),
    category: str | None = Query(default=None, description='Filter by product category'),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> list[ProductSummary]:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.inspections).selectinload(Inspection.findings),
            selectinload(Product.inspections).selectinload(Inspection.analysis_results),
        )
        .order_by(Product.created_at.desc())
    )

    if category and category.lower() != 'all':
        stmt = stmt.where(Product.category.ilike(category))

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(term),
                Product.brand.ilike(term),
                Product.manufacturer.ilike(term),
            )
        )

    products = db.scalars(stmt).all()

    results: list[ProductSummary] = []
    for p in products:
        metrics = compute_product_metrics(p)
        results.append(
            ProductSummary(
                id=p.id,
                name=p.name,
                category=p.category,
                brand=p.brand,
                manufacturer=p.manufacturer,
                description=p.description,
                created_at=p.created_at,
                updated_at=p.updated_at,
                inspection_count=metrics['inspection_count'],
                last_inspected_at=metrics['last_inspected_at'],
                compliance_score=metrics['compliance_score'],
                latest_verdict=metrics['latest_verdict'],
            )
        )
    return results


@router.post('', response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_CREATE)),
) -> Product:
    # Check if a product with exact matching name and brand already exists to prevent duplicate proliferation
    existing = db.scalars(
        select(Product).where(
            Product.name.ilike(payload.name.strip()),
            (Product.brand == payload.brand) | (Product.brand.ilike(payload.brand) if payload.brand else False),
        )
    ).first()

    if existing is not None:
        return existing

    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get('/{product_id}', response_model=ProductDetailResponse)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_READ)),
) -> ProductDetailResponse:
    product = db.scalars(
        select(Product)
        .options(
            selectinload(Product.inspections).selectinload(Inspection.findings),
            selectinload(Product.inspections).selectinload(Inspection.analysis_results),
        )
        .where(Product.id == product_id)
    ).first()

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    metrics = compute_product_metrics(product)
    sorted_inspections = sorted(
        product.inspections or [],
        key=lambda i: (i.created_at or datetime.min.replace(tzinfo=timezone.utc), i.inspection_number or ''),
        reverse=True,
    )

    inspection_records = [compute_inspection_record(i) for i in sorted_inspections]

    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        category=product.category,
        brand=product.brand,
        manufacturer=product.manufacturer,
        description=product.description,
        created_at=product.created_at,
        updated_at=product.updated_at,
        inspection_count=metrics['inspection_count'],
        last_inspected_at=metrics['last_inspected_at'],
        compliance_score=metrics['compliance_score'],
        latest_verdict=metrics['latest_verdict'],
        inspections=inspection_records,
    )


@router.patch('/{product_id}', response_model=ProductSummary)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> ProductSummary:
    product = db.scalars(
        select(Product)
        .options(
            selectinload(Product.inspections).selectinload(Inspection.findings),
            selectinload(Product.inspections).selectinload(Inspection.analysis_results),
        )
        .where(Product.id == product_id)
    ).first()

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(product, field, value)

    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)

    metrics = compute_product_metrics(product)
    return ProductSummary(
        id=product.id,
        name=product.name,
        category=product.category,
        brand=product.brand,
        manufacturer=product.manufacturer,
        description=product.description,
        created_at=product.created_at,
        updated_at=product.updated_at,
        inspection_count=metrics['inspection_count'],
        last_inspected_at=metrics['last_inspected_at'],
        compliance_score=metrics['compliance_score'],
        latest_verdict=metrics['latest_verdict'],
    )


@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INSPECTION_EDIT)),
) -> Response:

    product = db.scalars(
        select(Product)
        .options(selectinload(Product.inspections))
        .where(Product.id == product_id)
    ).first()

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')

    if product.inspections and len(product.inspections) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot delete product with existing inspection history',
        )

    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
