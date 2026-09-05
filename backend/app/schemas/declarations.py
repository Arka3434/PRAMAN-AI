from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.schemas.analysis_results import AnalysisResultRead
from app.schemas.inspections import InspectionComplianceSummary


class DeclarationsUpdateRequest(BaseModel):
    """
    Request payload for inspector field corrections on structured declarations.
    NOTE: Corrected values represent the inspector's verified input for
    deterministic statutory compliance re-evaluation. Raw OCR text and evidence
    regions remain immutable.
    """
    declarations: dict[str, Any] = Field(
        ...,
        description="Key-value mapping of declaration fields (e.g. commodity_name, retail_sale_price, net_quantity, etc.)"
    )
    notes: str | None = Field(
        None,
        description="Optional inspector audit note explaining the reason for correction"
    )


class DeclarationsUpdateResponse(BaseModel):
    """
    Response returned following declaration correction and deterministic re-evaluation.
    """
    inspection_id: str
    structured_declarations: dict[str, Any]
    raw_ocr_declarations: dict[str, Any]
    inspector_corrections: list[dict[str, Any]] = []
    compliance_summary: InspectionComplianceSummary
    analysis: AnalysisResultRead
