from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InspectionBase(BaseModel):
    inspection_number: str
    status: str = 'draft'
    title: str | None = None
    notes: str | None = None
    barcode_or_qr: str | None = None
    product_id: str | None = None
    inspector_id: str | None = None


class InspectionCreate(InspectionBase):
    pass


class InspectionRead(InspectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class InspectionHistoryItem(InspectionRead):
    product_name: str | None = None
    inspector_name: str | None = None
    finding_count: int = 0
    overall_result: str | None = None
    review_status: str | None = None
    report_available: bool = False
    notice_status: str | None = None
    notice_id: str | None = None
    notice_reference: str | None = None




class EngineSeverityDistribution(BaseModel):
    critical: int = 0
    major: int = 0
    warning: int = 0
    pass_count: int = 0


class EngineSummary(BaseModel):
    overall_result: str
    total_checks: int
    passed: int
    potential_violations: int
    warnings: int
    manual_review: int
    not_applicable: int = 0
    severity_distribution: EngineSeverityDistribution


class InspectorReviewSummary(BaseModel):
    total_findings: int
    reviewed_count: int
    pending_count: int
    confirmed_count: int
    rejected_count: int
    manual_review_count: int
    review_status: str


class FinalResultSummary(BaseModel):
    can_finalize: bool
    inspection_status: str
    blocking_reasons: list[str] = []


class InspectionComplianceSummary(BaseModel):
    inspection_id: str
    inspection_status: str
    inspection_date: str | None = None
    catalog_version: str | None = None
    catalog_hash: str | None = None
    engine_summary: EngineSummary
    inspector_summary: InspectorReviewSummary
    final_result: FinalResultSummary
