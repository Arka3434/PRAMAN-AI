from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewDecisionBase(BaseModel):
    inspection_id: str | None = None
    decision: str
    reviewer_name: str = 'demo-inspector'
    notes: str | None = None
    finding_id: str | None = None


class ReviewDecisionCreate(ReviewDecisionBase):
    pass


class ReviewDecisionRead(ReviewDecisionBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    comment: str | None = None
