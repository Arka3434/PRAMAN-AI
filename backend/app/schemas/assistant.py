"""PRAMAN Inspection Assistant Schemas

Defines read-only response DTOs for the deterministic evidence-grounded assistant.
Ensures no internal ORM objects leak and explicit disclaimers accompany all responses.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_ASSISTANT_DISCLAIMER = (
    "PRAMAN Assistant provides evidence-grounded informational assistance only. "
    "It does not determine legal liability, issue statutory notices, or replace authorized officer discretion."
)


class FindingExplanationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: str
    rule_check_id: str
    title: str
    rule_status: str
    inspector_decision: str | None = None
    inspector_decision_framing: str
    detected_value: Any | None = None
    expected_condition: str | None = None
    evidence_snippet: str | None = None
    evidence_panel: str | None = None
    ocr_confidence: float | None = None
    statutory_reference: str | None = None
    statutory_mapping_status: str
    statutory_mapping_explanation: str
    requires_human_review: bool = False
    human_review_reason: str | None = None
    applicable_legal_version: str | None = None
    disclaimer: str = Field(default=DEFAULT_ASSISTANT_DISCLAIMER)


class PanelQualityMetric(BaseModel):
    image_id: str
    panel: str
    assessment: str
    sharpness: float | None = None
    glare_score: float | None = None
    dimensions: str | None = None
    resolution_adequate: bool | None = None


class InspectionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_id: str
    inspection_number: str
    product_name: str | None = None
    applicable_legal_version: str | None = None
    panel_count: int = 0
    image_quality_assessments: list[PanelQualityMetric] = Field(default_factory=list)
    declaration_extraction_summary: dict[str, Any] = Field(default_factory=dict)
    engine_evaluation_summary: dict[str, int] = Field(default_factory=dict)
    inspector_review_summary: dict[str, int] = Field(default_factory=dict)
    unresolved_items: list[str] = Field(default_factory=list)
    statutory_notice_state: dict[str, Any] | None = None
    disclaimer: str = Field(default=DEFAULT_ASSISTANT_DISCLAIMER)


class EvidenceTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: str
    rule_check_id: str
    source_image_id: str | None = None
    source_panel: str | None = None
    ocr_snippet: str | None = None
    bounding_box: list[Any] | None = None
    ocr_confidence: float | None = None
    detected_value: Any | None = None
    declaration_field: str | None = None
    declaration_raw_text: str | None = None
    applicable_legal_version: str | None = None
    rule_description: str | None = None
    disclaimer: str = Field(default=DEFAULT_ASSISTANT_DISCLAIMER)


class ManualReviewItem(BaseModel):
    item_type: str
    identifier: str
    title: str
    reason: str
    available_evidence: list[str] = Field(default_factory=list)
    verification_checklist: list[str] = Field(default_factory=list)
    why_assistant_cannot_resolve: str


class ManualReviewGuideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_id: str
    manual_review_items: list[ManualReviewItem] = Field(default_factory=list)
    conflict_items: list[ManualReviewItem] = Field(default_factory=list)
    unresolved_discrepancies_count: int = 0
    guidance_notes: list[str] = Field(default_factory=list)
    disclaimer: str = Field(default=DEFAULT_ASSISTANT_DISCLAIMER)
