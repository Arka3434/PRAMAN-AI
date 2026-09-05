from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Inspection(Base):
    __tablename__ = 'inspections'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    inspection_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='draft', index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    barcode_or_qr: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey('products.id'), nullable=True, index=True)
    inspector_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    product: Mapped['Product | None'] = relationship(back_populates='inspections')
    inspector: Mapped['User | None'] = relationship(back_populates='inspections')
    images: Mapped[list['InspectionImage']] = relationship(back_populates='inspection', cascade='all, delete-orphan')
    analysis_results: Mapped[list['AnalysisResult']] = relationship(back_populates='inspection', cascade='all, delete-orphan')
    findings: Mapped[list['Finding']] = relationship(back_populates='inspection', cascade='all, delete-orphan')
    review_decisions: Mapped[list['ReviewDecision']] = relationship(back_populates='inspection', cascade='all, delete-orphan')
    notices: Mapped[list['Notice']] = relationship(back_populates='inspection')
