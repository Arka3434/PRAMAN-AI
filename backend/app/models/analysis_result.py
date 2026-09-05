from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisResult(Base):
    __tablename__ = 'analysis_results'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey('inspections.id'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='completed', index=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    structured_declarations: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True, default=0.0)
    ocr_regions: Mapped[dict | list | None] = mapped_column(JSON, nullable=True, default=list)
    extraction_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    inspection: Mapped['Inspection'] = relationship(back_populates='analysis_results')
