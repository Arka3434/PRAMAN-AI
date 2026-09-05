from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ComplianceTrendBucket(BaseModel):
    month: str
    pass_count: int = Field(..., serialization_alias='pass')
    warning_count: int = Field(..., serialization_alias='warning')
    violation_count: int = Field(..., serialization_alias='violation')

    class Config:
        populate_by_name = True


class CategoryBreakdownItem(BaseModel):
    name: str
    rule_id: str
    value: int
    fill: str


class DashboardRecentInspection(BaseModel):
    id: str
    inspection_number: str
    product_name: str | None
    inspector_name: str | None
    status: str
    score: str
    overall_result: str
    created_at: datetime


class DashboardAttentionItem(BaseModel):
    finding_id: str
    inspection_id: str
    inspection_number: str
    product_name: str | None
    title: str
    rule_check_id: str
    severity: str
    rule_status: str | None
    inspector_decision: str | None
    created_at: datetime


class DashboardOverviewResponse(BaseModel):
    # Statutory / Legal Metrics
    total_inspections: int
    inspections_this_month: int
    statutory_violations_count: int
    average_compliance_score: float | None  # 0.0 - 100.0, None if 0 analyzed
    compliance_trend: list[ComplianceTrendBucket]
    violation_breakdown: list[CategoryBreakdownItem]

    # Operational / Review Metrics
    review_queue_count: int
    recent_inspections: list[DashboardRecentInspection]
    attention_items: list[DashboardAttentionItem]


class RulePerformanceStat(BaseModel):
    rule_id: str
    rule_title: str
    total_evaluations: int
    pass_count: int
    violation_count: int
    warning_count: int
    manual_review_count: int
    pass_rate: float | None


class AnalyticsTrendsResponse(BaseModel):
    total_inspections: int
    total_completed: int
    total_in_review: int
    total_draft: int

    # Operational Review Adjudication
    total_findings: int
    reviewed_findings: int
    confirmed_violations: int
    rejected_findings: int
    manual_review_items: int
    adjudication_yield_rate: float

    compliance_trend: list[ComplianceTrendBucket]
    rule_performance: list[RulePerformanceStat]


class ViolationRegisterItem(BaseModel):
    finding_id: str
    inspection_id: str
    inspection_number: str
    product_name: str | None
    product_category: str | None
    title: str
    rule_check_id: str
    rule_title: str
    legal_citation: str
    severity: str
    rule_status: str | None
    inspector_decision: str | None
    detected_value: str | None
    created_at: datetime


class EscalationSummary(BaseModel):
    critical_violations: int
    major_violations: int
    statutory_warnings: int
    manual_review_required: int
    unreviewed_count: int
    confirmed_count: int
    rejected_count: int


class ViolationsRegisterResponse(BaseModel):
    items: list[ViolationRegisterItem]
    total: int
    limit: int
    offset: int
    summary: EscalationSummary
