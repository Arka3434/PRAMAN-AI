from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class StatutoryCharge(BaseModel):
    rule_id: str
    rule_citation: str
    defect_description: str
    statutory_provision: str
    liability_basis: str
    requires_manual_review: bool = False
    officer_notes: str | None = None
    finding_id: str | None = None


class EvidenceReference(BaseModel):
    image_id: str
    panel_type: str | None = None
    file_name: str
    sha256: str
    bounding_box: dict[str, Any] | None = None
    raw_snippet: str | None = None


class LegalVersionContext(BaseModel):
    catalog_version: str
    catalog_sha256: str
    effective_date: str


class NoticeDraftCreate(BaseModel):
    recipient_role: str | None = None
    recipient_name: str | None = None
    recipient_address: str | None = None
    establishment_name: str | None = None
    inspection_venue: str | None = None
    response_period_days: int | None = 15
    response_period_basis: str | None = "Configurable draft convenience for show-cause notice"
    compounding_eligible: bool = False
    compounding_clause_included: bool = False


class NoticeUpdate(BaseModel):
    recipient_role: str | None = None
    recipient_name: str | None = None
    recipient_address: str | None = None
    establishment_name: str | None = None
    inspection_venue: str | None = None
    response_period_days: int | None = None
    response_period_basis: str | None = None
    compounding_eligible: bool | None = None
    compounding_clause_included: bool | None = None
    compounding_available: bool | None = None
    statutory_charges: list[dict[str, Any]] | None = None
    officer_notes: str | None = None
    officer_review_notes: str | None = None

    @model_validator(mode='before')
    @classmethod
    def reconcile_update_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'compounding_available' in data and 'compounding_clause_included' not in data:
                data['compounding_clause_included'] = data['compounding_available']
            if 'officer_review_notes' in data and 'officer_notes' not in data:
                data['officer_notes'] = data['officer_review_notes']
        return data


class NoticeReviewRequest(BaseModel):
    officer_notes: str | None = None
    officer_review_notes: str | None = None
    reviewer_name: str | None = None

    @model_validator(mode='before')
    @classmethod
    def reconcile_notes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            notes = data.get('officer_notes') or data.get('officer_review_notes')
            if notes:
                data['officer_notes'] = notes
        return data


class NoticeIssueRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    officer_notes: str | None = None
    officer_review_notes: str | None = None

    @model_validator(mode='before')
    @classmethod
    def validate_and_reconcile(cls, data: Any) -> Any:
        if isinstance(data, dict):
            notes = data.get('officer_notes') or data.get('officer_review_notes')
            if notes:
                data['officer_notes'] = notes
        return data


class NoticeRead(BaseModel):
    id: str
    inspection_id: str
    notice_reference: str
    status: str
    recipient_role: str
    recipient_name: str
    recipient_address: str
    establishment_name: str | None = None
    inspection_venue: str | None = None
    statutory_charges: list[dict[str, Any]]
    legal_version_context: dict[str, Any]
    evidence_references: list[dict[str, Any]]
    inspection_snapshot: dict[str, Any]
    response_period_days: int | None = None
    response_period_basis: str | None = None
    compounding_eligible: bool
    compounding_clause_included: bool
    issuing_officer_id: str | None = None
    officer_name: str | None = None
    officer_designation: str | None = None
    officer_office: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    issued_at: datetime | None = None
    is_immutable: bool

    @computed_field
    @property
    def issuing_officer_name(self) -> str | None:
        return self.officer_name

    @computed_field
    @property
    def issuing_officer_designation(self) -> str | None:
        return self.officer_designation

    @computed_field
    @property
    def issuing_officer_jurisdiction(self) -> str | None:
        return self.officer_office

    @computed_field
    @property
    def compounding_available(self) -> bool:
        return self.compounding_clause_included

    model_config = ConfigDict(from_attributes=True)
