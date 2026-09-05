from __future__ import annotations

import calendar
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.review_decision import ReviewDecision
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsTrendsResponse,
    CategoryBreakdownItem,
    ComplianceTrendBucket,
    DashboardAttentionItem,
    DashboardOverviewResponse,
    DashboardRecentInspection,
    EscalationSummary,
    RulePerformanceStat,
    ViolationRegisterItem,
    ViolationsRegisterResponse,
)

router = APIRouter(prefix='/api/v1/analytics', tags=['analytics'])

# Standard category colors and labels for rule checks
RULE_CATEGORY_METADATA = {
    'PCR-001': {'name': 'Manufacturer / Packer Details', 'fill': '#1f6feb'},
    'PCR-002': {'name': 'Country of Origin', 'fill': '#0284c7'},
    'PCR-003': {'name': 'Generic Commodity Name', 'fill': '#8b5cf6'},
    'PCR-004': {'name': 'Net Quantity & Units', 'fill': '#ef4444'},
    'PCR-005': {'name': 'Month / Year of Packing', 'fill': '#f59e0b'},
    'PCR-006': {'name': 'Best Before / Expiry', 'fill': '#ec4899'},
    'PCR-007': {'name': 'Retail Sale Price & MRP', 'fill': '#dc2626'},
    'PCR-008': {'name': 'Display Panel & Typography', 'fill': '#64748b'},
}


def _calculate_inspection_score(findings: list[Finding]) -> float | None:
    """Calculate compliance score for a single inspection based strictly on engine rule_status.
    
    Numerator: findings where rule_status == 'PASS'.
    Denominator: findings where rule_status in ('PASS', 'POTENTIAL_VIOLATION', 'WARNING', 'MANUAL_REVIEW').
    NOT_APPLICABLE is excluded.
    Inspector review decisions NEVER convert a violation into a pass.
    """
    evaluated = [
        f for f in findings
        if f.rule_status in {'PASS', 'POTENTIAL_VIOLATION', 'WARNING', 'MANUAL_REVIEW'}
    ]
    if not evaluated:
        return None
    passed = sum(1 for f in evaluated if f.rule_status == 'PASS')
    return round((passed / len(evaluated)) * 100.0, 1)


@router.get('/overview', response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ANALYTICS_READ)),
) -> DashboardOverviewResponse:

    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Total inspections
    total_inspections = db.scalar(select(func.count(Inspection.id))) or 0

    # 2. Inspections this month
    inspections_this_month = db.scalar(
        select(func.count(Inspection.id)).where(Inspection.created_at >= first_of_month)
    ) or 0

    # 3. Load all inspections with findings & reviews for accurate score, review queue, and trends
    inspections = db.scalars(
        select(Inspection)
        .options(
            joinedload(Inspection.product),
            joinedload(Inspection.inspector),
            joinedload(Inspection.findings),
            joinedload(Inspection.review_decisions),
        )
        .order_by(Inspection.created_at.desc())
    ).unique().all()

    # 4. Review queue count & average compliance score
    review_queue_count = 0
    inspection_scores: list[float] = []

    for insp in inspections:
        findings = insp.findings or []
        finding_count = len(findings)

        # Review queue determination
        if insp.status != 'COMPLETED':
            if insp.status == 'REVIEW_REQUIRED':
                review_queue_count += 1
            elif finding_count > 0:
                reviewed_finding_ids = {rd.finding_id for rd in insp.review_decisions if rd.finding_id}
                unreviewed = any(f.id not in reviewed_finding_ids and f.status != 'resolved' for f in findings)
                if unreviewed:
                    review_queue_count += 1

        # Score determination
        score = _calculate_inspection_score(findings)
        if score is not None:
            inspection_scores.append(score)

    avg_score = round(sum(inspection_scores) / len(inspection_scores), 1) if inspection_scores else None

    # 5. Statutory violations count (rule_status == 'POTENTIAL_VIOLATION' across all findings)
    all_findings = [f for insp in inspections for f in insp.findings]
    statutory_violations_count = sum(1 for f in all_findings if f.rule_status == 'POTENTIAL_VIOLATION')

    # 6. Compliance Trend (past 6 calendar months)
    # Generate 6 chronological month buckets
    buckets: list[dict[str, int | str]] = []
    month_keys: list[tuple[int, int, str]] = []  # (year, month, month_str)

    start_date = (first_of_month - relativedelta(months=5))
    curr = start_date
    while curr <= now:
        month_label = curr.strftime('%b')
        month_keys.append((curr.year, curr.month, month_label))
        curr += relativedelta(months=1)

    bucket_data = {
        (y, m): {'month': label, 'pass': 0, 'warning': 0, 'violation': 0}
        for y, m, label in month_keys
    }

    for f in all_findings:
        if f.created_at:
            key = (f.created_at.year, f.created_at.month)
            if key in bucket_data:
                if f.rule_status == 'PASS':
                    bucket_data[key]['pass'] += 1
                elif f.rule_status == 'POTENTIAL_VIOLATION':
                    bucket_data[key]['violation'] += 1
                elif f.rule_status in {'WARNING', 'MANUAL_REVIEW'}:
                    bucket_data[key]['warning'] += 1

    compliance_trend = [
        ComplianceTrendBucket(
            month=str(bucket_data[k]['month']),
            pass_count=int(bucket_data[k]['pass']),
            warning_count=int(bucket_data[k]['warning']),
            violation_count=int(bucket_data[k]['violation']),
        )
        for k in [(y, m) for y, m, _ in month_keys]
    ]

    # 7. Violation Breakdown (by statutory rule_check_id where rule_status == 'POTENTIAL_VIOLATION')
    rule_violation_counts: dict[str, int] = {}
    for f in all_findings:
        if f.rule_status == 'POTENTIAL_VIOLATION':
            rule_violation_counts[f.rule_check_id] = rule_violation_counts.get(f.rule_check_id, 0) + 1

    violation_breakdown: list[CategoryBreakdownItem] = []
    for rule_id, count in sorted(rule_violation_counts.items(), key=lambda x: x[1], reverse=True):
        meta = RULE_CATEGORY_METADATA.get(rule_id, {'name': f'Rule {rule_id}', 'fill': '#64748b'})
        violation_breakdown.append(
            CategoryBreakdownItem(
                name=meta['name'],
                rule_id=rule_id,
                value=count,
                fill=meta['fill'],
            )
        )

    # 8. Recent Inspections (top 4 latest)
    recent_inspections: list[DashboardRecentInspection] = []
    for insp in inspections[:4]:
        prod_name = insp.product.name if insp.product else None
        insp_name = insp.inspector.full_name if insp.inspector else 'Field Officer'
        findings = insp.findings or []

        # Overall result calculation matching Phase 6H
        if not insp.analysis_results:
            overall_result = 'PENDING_ANALYSIS'
        elif any(f.rule_status == 'POTENTIAL_VIOLATION' for f in findings):
            overall_result = 'POTENTIAL_VIOLATIONS_DETECTED'
        elif any(f.rule_status in {'WARNING', 'MANUAL_REVIEW'} for f in findings):
            overall_result = 'WARNINGS_OR_MANUAL_REVIEW'
        else:
            overall_result = 'COMPLIANT'

        score_val = _calculate_inspection_score(findings)
        score_str = f'{score_val}%' if score_val is not None else '—'

        recent_inspections.append(
            DashboardRecentInspection(
                id=insp.id,
                inspection_number=insp.inspection_number,
                product_name=prod_name,
                inspector_name=insp_name,
                status=insp.status,
                score=score_str,
                overall_result=overall_result,
                created_at=insp.created_at,
            )
        )

    # 9. Attention Items (up to 3 latest open critical/major violations or manual review items)
    attention_items: list[DashboardAttentionItem] = []
    # Priority: open POTENTIAL_VIOLATION or MANUAL_REVIEW findings without confirmed/resolved decision
    candidate_attention = [
        f for f in all_findings
        if f.rule_status in {'POTENTIAL_VIOLATION', 'MANUAL_REVIEW'}
        and f.inspector_decision is None
    ]
    # Sort candidate findings by created_at desc
    candidate_attention.sort(key=lambda x: x.created_at, reverse=True)

    for f in candidate_attention[:3]:
        prod_name = f.inspection.product.name if f.inspection and f.inspection.product else None
        attention_items.append(
            DashboardAttentionItem(
                finding_id=f.id,
                inspection_id=f.inspection_id,
                inspection_number=f.inspection.inspection_number if f.inspection else 'INSP',
                product_name=prod_name,
                title=f.title,
                rule_check_id=f.rule_check_id,
                severity=f.severity,
                rule_status=f.rule_status,
                inspector_decision=f.inspector_decision,
                created_at=f.created_at,
            )
        )

    return DashboardOverviewResponse(
        total_inspections=total_inspections,
        inspections_this_month=inspections_this_month,
        statutory_violations_count=statutory_violations_count,
        review_queue_count=review_queue_count,
        average_compliance_score=avg_score,
        compliance_trend=compliance_trend,
        violation_breakdown=violation_breakdown,
        recent_inspections=recent_inspections,
        attention_items=attention_items,
    )


@router.get('/trends', response_model=AnalyticsTrendsResponse)
def get_analytics_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ANALYTICS_READ)),
) -> AnalyticsTrendsResponse:
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Inspection status counts
    inspections = db.scalars(
        select(Inspection)
        .options(
            joinedload(Inspection.findings),
            joinedload(Inspection.review_decisions),
        )
    ).unique().all()

    total_inspections = len(inspections)
    total_completed = sum(1 for i in inspections if i.status == 'COMPLETED')
    total_in_review = sum(1 for i in inspections if i.status == 'REVIEW_REQUIRED')
    total_draft = sum(1 for i in inspections if i.status == 'draft')

    all_findings = [f for insp in inspections for f in insp.findings]
    total_findings = len(all_findings)

    # Operational Adjudication Metrics
    reviewed_findings = 0
    confirmed_violations = 0
    rejected_findings = 0
    manual_review_items = 0

    for f in all_findings:
        dec = f.inspector_decision
        if dec:
            reviewed_findings += 1
            if dec == 'confirm':
                confirmed_violations += 1
            elif dec == 'reject':
                rejected_findings += 1
            elif dec == 'manual_review':
                manual_review_items += 1

    yield_rate = round((reviewed_findings / total_findings) * 100.0, 1) if total_findings > 0 else 0.0

    # Monthly trend
    start_date = (first_of_month - relativedelta(months=5))
    curr = start_date
    month_keys: list[tuple[int, int, str]] = []
    while curr <= now:
        month_keys.append((curr.year, curr.month, curr.strftime('%b')))
        curr += relativedelta(months=1)

    bucket_data = {
        (y, m): {'month': label, 'pass': 0, 'warning': 0, 'violation': 0}
        for y, m, label in month_keys
    }

    for f in all_findings:
        if f.created_at:
            key = (f.created_at.year, f.created_at.month)
            if key in bucket_data:
                if f.rule_status == 'PASS':
                    bucket_data[key]['pass'] += 1
                elif f.rule_status == 'POTENTIAL_VIOLATION':
                    bucket_data[key]['violation'] += 1
                elif f.rule_status in {'WARNING', 'MANUAL_REVIEW'}:
                    bucket_data[key]['warning'] += 1

    compliance_trend = [
        ComplianceTrendBucket(
            month=str(bucket_data[k]['month']),
            pass_count=int(bucket_data[k]['pass']),
            warning_count=int(bucket_data[k]['warning']),
            violation_count=int(bucket_data[k]['violation']),
        )
        for k in [(y, m) for y, m, _ in month_keys]
    ]

    # Rule-by-rule performance stats
    rule_stats_map: dict[str, dict[str, int]] = {}
    for f in all_findings:
        rid = f.rule_check_id
        if rid not in rule_stats_map:
            rule_stats_map[rid] = {'pass': 0, 'violation': 0, 'warning': 0, 'manual_review': 0}
        if f.rule_status == 'PASS':
            rule_stats_map[rid]['pass'] += 1
        elif f.rule_status == 'POTENTIAL_VIOLATION':
            rule_stats_map[rid]['violation'] += 1
        elif f.rule_status == 'WARNING':
            rule_stats_map[rid]['warning'] += 1
        elif f.rule_status == 'MANUAL_REVIEW':
            rule_stats_map[rid]['manual_review'] += 1

    rule_performance: list[RulePerformanceStat] = []
    for rid, s in sorted(rule_stats_map.items()):
        total_ev = s['pass'] + s['violation'] + s['warning'] + s['manual_review']
        p_rate = round((s['pass'] / total_ev) * 100.0, 1) if total_ev > 0 else None
        meta = RULE_CATEGORY_METADATA.get(rid, {'name': f'Rule {rid}'})
        rule_performance.append(
            RulePerformanceStat(
                rule_id=rid,
                rule_title=meta['name'],
                total_evaluations=total_ev,
                pass_count=s['pass'],
                violation_count=s['violation'],
                warning_count=s['warning'],
                manual_review_count=s['manual_review'],
                pass_rate=p_rate,
            )
        )

    return AnalyticsTrendsResponse(
        total_inspections=total_inspections,
        total_completed=total_completed,
        total_in_review=total_in_review,
        total_draft=total_draft,
        total_findings=total_findings,
        reviewed_findings=reviewed_findings,
        confirmed_violations=confirmed_violations,
        rejected_findings=rejected_findings,
        manual_review_items=manual_review_items,
        adjudication_yield_rate=yield_rate,
        compliance_trend=compliance_trend,
        rule_performance=rule_performance,
    )


@router.get('/violations', response_model=ViolationsRegisterResponse)
def get_violations_register(
    severity: str | None = Query(None, description='Filter by finding severity: critical, major, warning, pass'),
    rule_status: str | None = Query(None, description='Filter by statutory rule_status: POTENTIAL_VIOLATION, WARNING, MANUAL_REVIEW, PASS'),
    review_decision: str | None = Query(None, description='Filter by inspector review decision: unreviewed, confirm, reject, manual_review'),
    rule_id: str | None = Query(None, description='Filter by rule check ID: PCR-001, PCR-002, etc.'),
    search: str | None = Query(None, description='Search term matching product name, rule title, description, or inspection number'),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ANALYTICS_READ)),
) -> ViolationsRegisterResponse:
    # Query all findings joined with inspection and product
    stmt = (
        select(Finding)
        .join(Inspection, Finding.inspection_id == Inspection.id)
        .outerjoin(Product, Inspection.product_id == Product.id)
        .options(
            joinedload(Finding.inspection).joinedload(Inspection.product),
            joinedload(Finding.inspection).joinedload(Inspection.review_decisions),
        )
        .order_by(Finding.created_at.desc())
    )

    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if rule_id:
        stmt = stmt.where(Finding.rule_check_id == rule_id)

    findings = db.scalars(stmt).unique().all()

    # In-memory filtering for properties parsed from JSON evidence_reference & review_decisions
    filtered: list[Finding] = []
    for f in findings:
        # Filter by rule_status if requested
        if rule_status and f.rule_status != rule_status:
            continue

        # Filter by inspector review decision if requested
        dec = f.inspector_decision
        if review_decision:
            if review_decision == 'unreviewed' and dec is not None:
                continue
            elif review_decision != 'unreviewed' and dec != review_decision:
                continue

        # Filter by search string if requested
        if search and search.strip():
            term = search.strip().lower()
            prod_name = (f.inspection.product.name.lower() if f.inspection and f.inspection.product else '')
            insp_num = (f.inspection.inspection_number.lower() if f.inspection else '')
            title_text = f.title.lower()
            desc_text = f.description.lower()
            val_text = (f.detected_value.lower() if f.detected_value else '')
            if not any(term in s for s in (prod_name, insp_num, title_text, desc_text, val_text, f.rule_check_id.lower())):
                continue

        filtered.append(f)

    # Compute summary counts over all findings matching statutory criteria
    all_unfiltered = db.scalars(
        select(Finding).options(joinedload(Finding.inspection).joinedload(Inspection.review_decisions))
    ).unique().all()

    summary = EscalationSummary(
        critical_violations=sum(1 for f in all_unfiltered if f.severity == 'critical' and f.rule_status == 'POTENTIAL_VIOLATION'),
        major_violations=sum(1 for f in all_unfiltered if f.severity == 'major' and f.rule_status == 'POTENTIAL_VIOLATION'),
        statutory_warnings=sum(1 for f in all_unfiltered if f.rule_status == 'WARNING'),
        manual_review_required=sum(1 for f in all_unfiltered if f.rule_status == 'MANUAL_REVIEW'),
        unreviewed_count=sum(1 for f in all_unfiltered if f.rule_status in {'POTENTIAL_VIOLATION', 'MANUAL_REVIEW'} and f.inspector_decision is None),
        confirmed_count=sum(1 for f in all_unfiltered if f.inspector_decision == 'confirm'),
        rejected_count=sum(1 for f in all_unfiltered if f.inspector_decision == 'reject'),
    )

    total_count = len(filtered)
    paginated = filtered[offset : offset + limit]

    items: list[ViolationRegisterItem] = []
    for f in paginated:
        prod = f.inspection.product if f.inspection else None
        meta = RULE_CATEGORY_METADATA.get(f.rule_check_id, {'name': f'Rule {f.rule_check_id}'})
        items.append(
            ViolationRegisterItem(
                finding_id=f.id,
                inspection_id=f.inspection_id,
                inspection_number=f.inspection.inspection_number if f.inspection else 'INSP',
                product_name=prod.name if prod else None,
                product_category=prod.category if prod else None,
                title=f.title,
                rule_check_id=f.rule_check_id,
                rule_title=meta['name'],
                legal_citation=f.legal_citation,
                severity=f.severity,
                rule_status=f.rule_status,
                inspector_decision=f.inspector_decision,
                detected_value=f.detected_value,
                created_at=f.created_at,
            )
        )

    return ViolationsRegisterResponse(
        items=items,
        total=total_count,
        limit=limit,
        offset=offset,
        summary=summary,
    )
