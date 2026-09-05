from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    name: str
    category: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    description: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    description: str | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class ProductSummary(ProductRead):
    inspection_count: int = 0
    last_inspected_at: datetime | None = None
    compliance_score: float | None = None
    latest_verdict: str | None = None


class ProductInspectionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_number: str
    status: str
    created_at: datetime
    overall_result: str | None = None
    finding_count: int = 0
    report_available: bool = False


class ProductDetailResponse(ProductSummary):
    inspections: list[ProductInspectionRecord] = []
