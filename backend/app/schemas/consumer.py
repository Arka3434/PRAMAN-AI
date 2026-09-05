from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class ConsumerProductSummary(BaseModel):
    id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None


class ConsumerDeclarationItem(BaseModel):
    field_key: str
    field_label: str
    status: str  # "Detected" | "Not detected in this image" | "Image quality insufficient" | "Not applicable / unknown"
    detected_value: Optional[str] = None
    description: str


class ConsumerProductDetail(ConsumerProductSummary):
    declarations: List[ConsumerDeclarationItem] = Field(default_factory=list)
    consumer_notice: str


class ConsumerQualityInfo(BaseModel):
    quality_verdict: str  # "ACCEPTABLE", "WARNING_DEGRADED", "UNREADABLE"
    quality_notes: str
    is_sufficient_for_scan: bool


class ConsumerScanResponse(BaseModel):
    scan_id: str
    image_name: Optional[str] = None
    quality: ConsumerQualityInfo
    declarations: List[ConsumerDeclarationItem] = Field(default_factory=list)
    detected_commodity_name: Optional[str] = None
    consumer_notice: str
