from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisResultBase(BaseModel):
    inspection_id: str
    status: str = 'completed'
    confidence: float = 0.0
    structured_declarations: dict[str, Any] = {}
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    ocr_regions: list[dict[str, Any]] = []
    extraction_metadata: dict[str, Any] = {}


class AnalysisResultCreate(AnalysisResultBase):
    pass


class AnalysisResultRead(AnalysisResultBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
