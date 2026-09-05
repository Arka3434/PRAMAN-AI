from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FindingBase(BaseModel):
    inspection_id: str
    severity: str = 'warning'
    status: str = 'open'
    title: str
    description: str
    detected_value: str | None = None
    rule_check_id: str
    evidence_reference: str | None = None
    rule_status: str | None = None
    panel_type: str | None = None
    has_conflict: bool | None = None

    # Phase 6D.1 Explainability fields (optional with defaults for full backward compatibility)
    what: str | None = None
    why: str | None = None
    legal_citation: str | None = None
    expected_condition: str | None = None
    source_image: str | None = None
    storage_path: str | None = None
    image_id: str | None = None
    evidence_snippet: str | None = None
    evidence_location: list[Any] | None = None
    ocr_confidence: float | None = None

    # Phase 6D.3 Inspector review fields
    inspector_decision: str | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    inspector_notes: str | None = None


class FindingCreate(FindingBase):
    pass


class FindingRead(FindingBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
