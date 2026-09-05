from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_RULE_CATALOG_CACHE: dict[str, dict[str, Any]] | None = None


def _get_rule_catalog() -> dict[str, dict[str, Any]]:
    global _RULE_CATALOG_CACHE
    if _RULE_CATALOG_CACHE is None:
        catalog_path = (
            Path(__file__).resolve().parents[3]
            / 'legal'
            / 'rule_catalog'
            / 'rules_v1.json'
        )
        if catalog_path.exists():
            try:
                data = json.loads(catalog_path.read_text(encoding='utf-8'))
                _RULE_CATALOG_CACHE = {
                    r['rule_id']: r for r in data.get('rules', [])
                }
            except Exception:
                _RULE_CATALOG_CACHE = {}
        else:
            _RULE_CATALOG_CACHE = {}
    return _RULE_CATALOG_CACHE


class Finding(Base):
    __tablename__ = 'findings'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    inspection_id: Mapped[str] = mapped_column(ForeignKey('inspections.id'), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default='warning', index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='open', index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rule_check_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    inspection: Mapped['Inspection'] = relationship(back_populates='findings')

    @property
    def _evidence_dict(self) -> dict[str, Any]:
        if not self.evidence_reference:
            return {}
        ref = self.evidence_reference.strip()
        if ref.startswith('{') and ref.endswith('}'):
            try:
                parsed = json.loads(ref)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {'source_image': ref, 'source_file': ref}

    @property
    def what(self) -> str:
        """Plain-language issue or result."""
        return self.description

    @property
    def why(self) -> str:
        """Statutory legal rationale."""
        cat = _get_rule_catalog().get(self.rule_check_id)
        if cat:
            return (
                f"Statutory requirement under {cat.get('legal_citation', '')}. "
                f"Expected condition: {cat.get('expected_condition', '')}"
            )
        return f"Statutory requirement under Legal Metrology Rules for {self.rule_check_id}."

    @property
    def legal_citation(self) -> str:
        cat = _get_rule_catalog().get(self.rule_check_id)
        if cat and cat.get('legal_citation'):
            return str(cat['legal_citation'])
        return f"Legal Metrology (Packaged Commodities) Rules, 2011, {self.rule_check_id}"

    @property
    def expected_condition(self) -> str:
        cat = _get_rule_catalog().get(self.rule_check_id)
        if cat and cat.get('expected_condition'):
            return str(cat['expected_condition'])
        return "Mandatory statutory declaration required."

    @property
    def source_image(self) -> str | None:
        return self._evidence_dict.get('source_image') or self._evidence_dict.get('source_file')

    @property
    def evidence_snippet(self) -> str | None:
        return self._evidence_dict.get('evidence_snippet')

    @property
    def evidence_location(self) -> list[Any] | None:
        return self._evidence_dict.get('evidence_location')

    @property
    def ocr_confidence(self) -> float | None:
        conf = self._evidence_dict.get('ocr_confidence')
        if conf is not None:
            try:
                return float(conf)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def storage_path(self) -> str | None:
        return self._evidence_dict.get('storage_path')

    @property
    def image_id(self) -> str | None:
        return self._evidence_dict.get('image_id')

    @property
    def rule_status(self) -> str | None:
        return self._evidence_dict.get('rule_status')

    @property
    def panel_type(self) -> str | None:
        return self._evidence_dict.get('panel_type')

    @property
    def has_conflict(self) -> bool:
        return bool(self._evidence_dict.get('has_conflict', False))

    @property
    def _latest_review_decision(self) -> Any | None:
        if not self.inspection or not getattr(self.inspection, 'review_decisions', None):
            return None
        # Check for finding-specific review decision first (most recent)
        for rd in sorted(self.inspection.review_decisions, key=lambda x: x.created_at, reverse=True):
            if rd.finding_id == self.id:
                return rd
        # Fall back to overall inspection review decision (most recent where finding_id is None and created after finding)
        for rd in sorted(self.inspection.review_decisions, key=lambda x: x.created_at, reverse=True):
            if rd.finding_id is None and (rd.created_at >= self.created_at):
                return rd
        return None

    @property
    def inspector_decision(self) -> str | None:
        rd = self._latest_review_decision
        return rd.decision if rd else None

    @property
    def reviewer_name(self) -> str | None:
        rd = self._latest_review_decision
        return rd.reviewer_name if rd else None

    @property
    def reviewed_at(self) -> datetime | None:
        rd = self._latest_review_decision
        return rd.created_at if rd else None

    @property
    def inspector_notes(self) -> str | None:
        rd = self._latest_review_decision
        return rd.comment if rd else None

