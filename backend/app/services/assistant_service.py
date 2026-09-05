"""Deterministic Evidence Assistant Service

Provides deterministic, read-only explanations, summaries, evidence traces,
and manual-review guides grounded strictly in existing inspection records,
declarations, image quality metadata, and stored statutory notice records.

Non-negotiable invariants:
- Read-only: Does not modify any database records or statuses.
- No LLM/generative AI: Fully deterministic logic.
- No legal inference: Does not invent PCR-to-Act statutory mappings or penalty amounts.
- Clear administrative distinction: Inspector reviews are treated as administrative confirmation,
  not judicial determinations of legal guilt.
"""

import json
from pathlib import Path
from typing import Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.inspection_image import InspectionImage
from app.models.notice import Notice
from app.schemas.assistant import (
    DEFAULT_ASSISTANT_DISCLAIMER,
    EvidenceTraceResponse,
    FindingExplanationResponse,
    InspectionSummaryResponse,
    ManualReviewGuideResponse,
    ManualReviewItem,
    PanelQualityMetric,
)
from app.services.quality_service import load_quality_metadata

_RULE_CATALOG_CACHE: dict[str, dict[str, Any]] | None = None


def _get_rule_catalog() -> dict[str, dict[str, Any]]:
    global _RULE_CATALOG_CACHE
    if _RULE_CATALOG_CACHE is None:
        catalog_path = (
            Path(__file__).resolve().parents[3]
            / "legal"
            / "rule_catalog"
            / "rules_v1.json"
        )
        if catalog_path.exists():
            try:
                data = json.loads(catalog_path.read_text(encoding="utf-8"))
                _RULE_CATALOG_CACHE = {
                    r["rule_id"]: r for r in data.get("rules", [])
                }
            except Exception:
                _RULE_CATALOG_CACHE = {}
        else:
            _RULE_CATALOG_CACHE = {}
    return _RULE_CATALOG_CACHE


class DeterministicEvidenceAssistant:
    """Read-only deterministic assistant for PRAMAN inspections."""

    def __init__(self, db: Session):
        self.db = db

    def _get_inspection(self, inspection_id: str) -> Inspection:
        inspection = self.db.get(Inspection, inspection_id)
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
        return inspection

    def _get_finding(self, inspection_id: str, finding_id: str) -> Finding:
        finding = self.db.get(Finding, finding_id)
        if not finding or finding.inspection_id != inspection_id:
            raise HTTPException(status_code=404, detail="Finding not found for this inspection")
        return finding

    def explain_finding(self, inspection_id: str, finding_id: str) -> FindingExplanationResponse:
        """Explains an existing finding using stored evidence, rules, and notice records."""
        self._get_inspection(inspection_id)
        finding = self._get_finding(inspection_id, finding_id)

        # 1. Fetch catalog rule context
        catalog_rule = _get_rule_catalog().get(finding.rule_check_id)

        # 2. Frame inspector decision administratively
        inspector_dec = finding.inspector_decision
        if inspector_dec:
            framing = (
                f"Administrative inspector review: {inspector_dec.capitalize()} finding "
                "(records human officer administrative review; does not constitute judicial determination of legal guilt)"
            )
        else:
            framing = "Pending inspector administrative review (no human verification recorded yet)"

        # 3. Check for existing authoritative statutory mapping in stored Notice records
        existing_notice = (
            self.db.query(Notice)
            .filter(Notice.inspection_id == inspection_id)
            .order_by(Notice.created_at.desc())
            .first()
        )

        statutory_reference = None
        statutory_mapping_status = "MANUAL_LEGAL_REVIEW_REQUIRED"
        statutory_mapping_explanation = (
            "No statutory mapping is currently recorded in an authorized notice for this finding. "
            "Determining Legal Metrology Act sections or liability requires human officer and legal review. "
            "The assistant does not independently infer statutory mappings."
        )

        if existing_notice and existing_notice.statutory_charges:
            for charge in existing_notice.statutory_charges:
                charge_dict = charge if isinstance(charge, dict) else {}
                if (
                    charge_dict.get("finding_id") == finding.id
                    or charge_dict.get("rule_code") == finding.rule_check_id
                    or charge_dict.get("rule_id") == finding.rule_check_id
                ):
                    act_sec = (
                        charge_dict.get("statutory_provision")
                        or charge_dict.get("act_section")
                        or charge_dict.get("section")
                    )
                    legal_basis = (
                        charge_dict.get("liability_basis")
                        or charge_dict.get("legal_basis")
                        or charge_dict.get("description", "")
                    )
                    statutory_reference = act_sec
                    statutory_mapping_status = "RECORDED_IN_NOTICE"
                    statutory_mapping_explanation = (
                        f"Authoritative statutory charge recorded in Notice ({existing_notice.status}): "
                        f"{act_sec}. {legal_basis}"
                    )
                    break

        # 4. Determine human review necessity
        status_val = finding.rule_status or "FAIL"
        requires_human_review = (
            status_val in ("MANUAL_REVIEW", "REQUIRES_PHYSICAL_VERIFICATION")
            or inspector_dec is None
            or status_val == "FAIL"
        )
        human_review_reason = None
        if status_val in ("MANUAL_REVIEW", "REQUIRES_PHYSICAL_VERIFICATION"):
            human_review_reason = (
                "Finding is flagged for manual/physical verification. Physical measurement or "
                "contextual inspection cannot be determined from optical/declaration data alone."
            )
        elif inspector_dec is None:
            human_review_reason = "Awaiting human officer administrative review to confirm or override engine finding."
        elif status_val == "FAIL":
            human_review_reason = (
                "Potential non-compliance flagged by engine. Human officer verification is required "
                "before any administrative or statutory action can be initiated."
            )

        expected_condition = (
            catalog_rule.get("expected_condition")
            if catalog_rule
            else finding.expected_condition
        )

        applicable_version = (
            catalog_rule.get("version", "PCR-2011-consolidated") if catalog_rule else "PCR-2011-consolidated"
        )

        return FindingExplanationResponse(
            finding_id=finding.id,
            rule_check_id=finding.rule_check_id,
            title=finding.title,
            rule_status=status_val,
            inspector_decision=inspector_dec,
            inspector_decision_framing=framing,
            detected_value=finding.detected_value,
            expected_condition=expected_condition,
            evidence_snippet=finding.evidence_snippet,
            evidence_panel=finding.panel_type,
            ocr_confidence=finding.ocr_confidence,
            statutory_reference=statutory_reference,
            statutory_mapping_status=statutory_mapping_status,
            statutory_mapping_explanation=statutory_mapping_explanation,
            requires_human_review=requires_human_review,
            human_review_reason=human_review_reason,
            applicable_legal_version=applicable_version,
            disclaimer=DEFAULT_ASSISTANT_DISCLAIMER,
        )

    def summarize_inspection(self, inspection_id: str) -> InspectionSummaryResponse:
        """Summarizes an inspection deterministically based on existing stored data."""
        inspection = self._get_inspection(inspection_id)

        # 1. Quality metrics per panel
        quality_assessments: list[PanelQualityMetric] = []
        for img in inspection.images:
            report = None
            if img.storage_path:
                report = load_quality_metadata(img.storage_path)
            panel_name = getattr(img, "panel_type", None) or getattr(img, "image_type", "PRIMARY")
            verdict_str = report.quality_verdict.value if report else "UNASSESSED"
            sharpness_val = report.sharpness_score if report else None
            glare_val = report.glare_percentage if report else None
            dim_str = (
                f"{report.width}x{report.height}"
                if report and report.width and report.height
                else (f"{img.width}x{img.height}" if img.width and img.height else None)
            )
            res_adequate = report.resolution_adequate if report else None
            quality_assessments.append(
                PanelQualityMetric(
                    image_id=img.id,
                    panel=panel_name or "PRIMARY",
                    assessment=verdict_str,
                    sharpness=sharpness_val,
                    glare_score=glare_val,
                    dimensions=dim_str,
                    resolution_adequate=res_adequate,
                )
            )

        # 2. Declaration extraction summary
        extracted_fields: list[str] = []
        if inspection.analysis_results:
            latest_ar = inspection.analysis_results[0]
            if latest_ar.structured_declarations and isinstance(latest_ar.structured_declarations, dict):
                extracted_fields = list(latest_ar.structured_declarations.keys())

        decl_summary = {
            "total_extracted": len(extracted_fields),
            "extracted_fields": extracted_fields,
            "has_multipanel_provenance": len(inspection.images) > 1,
        }

        # 3. Engine evaluation summary
        findings = inspection.findings
        engine_eval: dict[str, int] = {}
        inspector_eval: dict[str, int] = {"PENDING": 0, "CONFIRMED": 0, "REJECTED": 0, "OVERRIDDEN": 0}

        unresolved_items: list[str] = []
        for f in findings:
            status_val = f.rule_status or "FAIL"
            engine_eval[status_val] = engine_eval.get(status_val, 0) + 1
            if f.inspector_decision:
                dec = f.inspector_decision.upper()
                inspector_eval[dec] = inspector_eval.get(dec, 0) + 1
            else:
                inspector_eval["PENDING"] += 1
                unresolved_items.append(f"Finding {f.rule_check_id} ({f.title}) pending inspector review")

            if status_val in ("MANUAL_REVIEW", "REQUIRES_PHYSICAL_VERIFICATION"):
                unresolved_items.append(f"Rule check {f.rule_check_id} requires physical/manual verification")

        for qa in quality_assessments:
            if qa.assessment in ("WARNING_DEGRADED", "UNREADABLE"):
                unresolved_items.append(
                    f"Panel {qa.panel} image quality is {qa.assessment}; optical declarations may be degraded"
                )

        # 4. Statutory notice state
        existing_notice = (
            self.db.query(Notice)
            .filter(Notice.inspection_id == inspection_id)
            .order_by(Notice.created_at.desc())
            .first()
        )
        notice_state = None
        if existing_notice:
            notice_state = {
                "id": existing_notice.id,
                "notice_number": existing_notice.notice_reference,
                "status": existing_notice.status,
                "is_immutable": existing_notice.is_immutable,
                "charges_count": len(existing_notice.statutory_charges) if existing_notice.statutory_charges else 0,
                "officer_name": existing_notice.officer_name,
            }

        product_name = inspection.product.name if inspection.product else None
        applicable_version = "PCR-2011-consolidated"

        return InspectionSummaryResponse(
            inspection_id=inspection.id,
            inspection_number=inspection.inspection_number,
            product_name=product_name,
            applicable_legal_version=applicable_version,
            panel_count=len(inspection.images),
            image_quality_assessments=quality_assessments,
            declaration_extraction_summary=decl_summary,
            engine_evaluation_summary=engine_eval,
            inspector_review_summary=inspector_eval,
            unresolved_items=unresolved_items,
            statutory_notice_state=notice_state,
            disclaimer=DEFAULT_ASSISTANT_DISCLAIMER,
        )

    def trace_evidence(self, inspection_id: str, finding_id: str) -> EvidenceTraceResponse:
        """Traces the optical and declaration evidence underlying an evaluation."""
        self._get_inspection(inspection_id)
        finding = self._get_finding(inspection_id, finding_id)

        catalog_rule = _get_rule_catalog().get(finding.rule_check_id)

        source_image_id = finding.image_id
        source_panel = finding.panel_type
        ocr_snippet = finding.evidence_snippet
        ocr_confidence = finding.ocr_confidence
        bbox = finding.evidence_location
        detected_val = finding.detected_value

        return EvidenceTraceResponse(
            finding_id=finding.id,
            rule_check_id=finding.rule_check_id,
            source_image_id=source_image_id,
            source_panel=source_panel,
            ocr_snippet=ocr_snippet,
            bounding_box=bbox,
            ocr_confidence=ocr_confidence,
            detected_value=detected_val,
            declaration_field=finding.rule_check_id,
            declaration_raw_text=ocr_snippet,
            applicable_legal_version=catalog_rule.get("version", "PCR-2011-consolidated") if catalog_rule else "PCR-2011-consolidated",
            rule_description=catalog_rule.get("description") if catalog_rule else finding.description,
            disclaimer=DEFAULT_ASSISTANT_DISCLAIMER,
        )

    def get_manual_review_guide(self, inspection_id: str) -> ManualReviewGuideResponse:
        """Generates guidance on manual review and physical verification items."""
        inspection = self._get_inspection(inspection_id)

        manual_items: list[ManualReviewItem] = []
        conflict_items: list[ManualReviewItem] = []

        # 1. Findings requiring manual or physical review
        for f in inspection.findings:
            status_val = f.rule_status or "FAIL"
            if status_val in ("MANUAL_REVIEW", "REQUIRES_PHYSICAL_VERIFICATION") or f.has_conflict:
                if "net_quantity" in f.rule_check_id.lower() or "weight" in f.rule_check_id.lower() or "003" in f.rule_check_id:
                    reason = (
                        "Net quantity compliance under Section 36(2) of the Legal Metrology Act requires physical "
                        "verification using calibrated standard weights. Label declaration alone does not verify actual net contents."
                    )
                    evidence = [f.evidence_snippet or "Declared net quantity on packaging"]
                    checklist = [
                        "Perform physical measurement using calibrated working standard balance.",
                        "Verify tare weight of empty packaging material.",
                        "Check Maximum Permissible Error (MPE) tolerances under the Second Schedule of PCR, 2011.",
                        "Record formal weight determination on physical inspection memo.",
                    ]
                    why = (
                        "Physical mass/volume verification requires physical instruments. "
                        "Camera and OCR data cannot measure actual container contents."
                    )
                else:
                    reason = f"Rule check {f.rule_check_id} flagged for human verification: {f.description or f.title}"
                    evidence = [f.evidence_snippet] if f.evidence_snippet else []
                    checklist = [
                        "Review packaging in physical custody.",
                        "Verify legibility and prominence of declaration.",
                        "Record inspector decision on the workflow page.",
                    ]
                    why = "Automated vision confidence or rule heuristic requires human officer confirmation."

                manual_items.append(
                    ManualReviewItem(
                        item_type="FINDING_MANUAL_REVIEW",
                        identifier=f.rule_check_id,
                        title=f.title,
                        reason=reason,
                        available_evidence=evidence,
                        verification_checklist=checklist,
                        why_assistant_cannot_resolve=why,
                    )
                )

        # 2. Check for multi-panel discrepancies or degraded images
        for img in inspection.images:
            report = None
            if img.storage_path:
                report = load_quality_metadata(img.storage_path)
            if report and report.quality_verdict.value in ("WARNING_DEGRADED", "UNREADABLE"):
                panel_name = getattr(img, "panel_type", None) or getattr(img, "image_type", "PRIMARY")
                conflict_items.append(
                    ManualReviewItem(
                        item_type="IMAGE_DEGRADATION",
                        identifier=img.id,
                        title=f"Degraded Image on Panel: {panel_name}",
                        reason=(
                            f"Image quality is assessed as {report.quality_verdict.value} "
                            f"(sharpness: {report.sharpness_score}, glare: {report.glare_percentage}%). "
                            "OCR and declaration extraction may be incomplete or degraded."
                        ),
                        available_evidence=[f"Stored image ID: {img.id}, Panel: {panel_name}"],
                        verification_checklist=[
                            "Inspect the physical packaging directly under proper lighting.",
                            "Capture a higher-resolution, glare-free replacement image if needed.",
                            "Manually verify any declarations located on this package panel.",
                        ],
                        why_assistant_cannot_resolve=(
                            "Optical image degradation prevents deterministic text extraction. "
                            "Human physical inspection is required to verify degraded packaging surfaces."
                        ),
                    )
                )

        guidance_notes = [
            "Manual review items must be verified directly by an authorized inspector.",
            "The assistant explains available evidence but does not resolve conflicts or determine compliance.",
            "Never infer physical net-quantity liability under Section 36(2) from OCR declarations alone.",
        ]

        return ManualReviewGuideResponse(
            inspection_id=inspection.id,
            manual_review_items=manual_items,
            conflict_items=conflict_items,
            unresolved_discrepancies_count=len(manual_items) + len(conflict_items),
            guidance_notes=guidance_notes,
            disclaimer=DEFAULT_ASSISTANT_DISCLAIMER,
        )
