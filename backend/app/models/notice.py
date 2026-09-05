from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notice(Base):
    __tablename__ = 'notices'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey('inspections.id'), nullable=False, index=True)
    notice_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='DRAFT', index=True)  # DRAFT, REVIEWED, ISSUED_BY_OFFICER
    recipient_role: Mapped[str] = mapped_column(String(64), nullable=False, default='unknown_pending_verification')
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_address: Mapped[str] = mapped_column(Text, nullable=False)
    establishment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inspection_venue: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Structured audit & statutory payload
    statutory_charges: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    legal_version_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    inspection_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Configurable procedural terms
    response_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True, default=15)
    response_period_basis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    compounding_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    compounding_clause_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Officer identification & audit linkage
    issuing_officer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    officer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    officer_designation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    officer_office: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps & locking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    inspection: Mapped['Inspection'] = relationship(back_populates='notices')
    issuing_officer: Mapped['User | None'] = relationship()


from sqlalchemy import event


@event.listens_for(Notice, 'before_delete')
def prevent_issued_notice_deletion(mapper: Any, connection: Any, target: Notice) -> None:
    if target.is_immutable or target.status == 'ISSUED_BY_OFFICER':
        raise ValueError(
            'Cannot delete an issued statutory notice. Historical statutory records are permanently preserved.'
        )
