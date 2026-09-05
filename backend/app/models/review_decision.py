import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewDecision(Base):
    __tablename__ = 'review_decisions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey('inspections.id'), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    reviewer_name: Mapped[str] = mapped_column(String(150), nullable=False, default='demo-inspector')
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    inspection: Mapped['Inspection'] = relationship(back_populates='review_decisions')
    reviewer: Mapped['User | None'] = relationship()

    @property
    def finding_id(self) -> str | None:
        if not self.notes:
            return None
        trimmed = self.notes.strip()
        if trimmed.startswith('{') and trimmed.endswith('}'):
            try:
                parsed = json.loads(trimmed)
                if isinstance(parsed, dict):
                    return parsed.get('finding_id')
            except Exception:
                pass
        return None

    @property
    def comment(self) -> str | None:
        if not self.notes:
            return None
        trimmed = self.notes.strip()
        if trimmed.startswith('{') and trimmed.endswith('}'):
            try:
                parsed = json.loads(trimmed)
                if isinstance(parsed, dict) and 'finding_id' in parsed:
                    return parsed.get('notes')
            except Exception:
                pass
        return self.notes
