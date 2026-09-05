from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


from typing import Optional
from app.schemas.quality import ImageQualityReport


class InspectionImageBase(BaseModel):
    inspection_id: str
    image_type: str = 'primary'
    file_name: str
    storage_path: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None


class InspectionImageCreate(InspectionImageBase):
    pass


class InspectionImageRead(InspectionImageBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    quality_assessment: Optional[ImageQualityReport] = None
    rotation_metadata: Optional[dict] = None

