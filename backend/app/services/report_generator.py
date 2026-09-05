"""Phase 6G: Evidence-Backed Inspection Report Generator.

Generates a formal, professional PDF inspection report using ReportLab.
Aggregates deterministic compliance findings, inspector decisions, statutory citations,
and visual evidence annotations into an authoritative audit document.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image as PILImage, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.finding import Finding
from app.models.inspection import Inspection


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and render total page count and running headers/footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(page_count)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#334155"))
            self.drawString(54, 750, "PRAMAN — Legal Metrology Inspection Report")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawRightString(558, 750, "Statutory PCR 2011 Audit")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Running Footer (all pages)
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(54, 34, "CONFIDENTIAL & STATUTORY • PRAMAN AI-Assisted Compliance Engine")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 34, page_text)

        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 44, 558, 44)

        self.restoreState()


class InspectionReportGenerator:
    """Service to generate deterministic evidence-backed PDF inspection reports."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        self.title_style = ParagraphStyle(
            'DocTitle',
            parent=self.styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=3,
        )
        self.subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor('#475569'),
            spaceAfter=8,
        )
        self.section_heading = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=8,
            spaceAfter=4,
        )
        self.body_style = ParagraphStyle(
            'BodyRegular',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor('#1E293B'),
        )
        self.body_bold = ParagraphStyle(
            'BodyBold',
            parent=self.body_style,
            fontName='Helvetica-Bold',
        )
        self.caption_style = ParagraphStyle(
            'Caption',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#64748B'),
        )
        self.statutory_citation = ParagraphStyle(
            'Citation',
            parent=self.styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor('#0369A1'),
        )
        self.disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            leading=9.5,
            textColor=colors.HexColor('#475569'),
        )

    def generate_pdf(
        self,
        inspection: Inspection,
        findings: list[Finding],
        summary: dict[str, Any],
        storage_base_path: str | Path | None = None,
    ) -> bytes:
        """Generates the full PDF report as raw bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        elements: list[Any] = []

        # 1. Header Banner
        elements.extend(self._build_header_banner(inspection, summary))
        elements.append(Spacer(1, 10))

        # 2. Inspection & Product Metadata Grid
        elements.extend(self._build_metadata_section(inspection, summary))
        elements.append(Spacer(1, 10))

        # 3. Executive Compliance Summary (Engine vs Inspector vs Final)
        elements.extend(self._build_compliance_summary_section(summary))
        elements.append(Spacer(1, 12))

        # 4. Detailed Statutory Findings & Visual Evidence
        elements.extend(self._build_findings_section(findings, storage_base_path))
        elements.append(Spacer(1, 12))

        # 5. Legal Authority & Disclaimer Notice
        elements.extend(self._build_legal_disclaimer(summary))

        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()

    def _build_header_banner(self, inspection: Inspection, summary: dict[str, Any]) -> list[Any]:
        items: list[Any] = []

        header_data = [
            [
                Paragraph("<b>PRAMAN</b> | Statutory Inspection Report", self.title_style),
                Paragraph(
                    f"<b>Inspection Ref:</b> {inspection.inspection_number}<br/>"
                    f"<b>Status:</b> {inspection.status}",
                    ParagraphStyle(
                        'RightHead',
                        parent=self.body_style,
                        alignment=2,
                        textColor=colors.HexColor('#0F172A'),
                    ),
                ),
            ],
            [
                Paragraph(
                    "Legal Metrology (Packaged Commodities) Rules, 2011 Compliance Audit",
                    self.subtitle_style,
                ),
                Paragraph(
                    f"<b>Date:</b> {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M UTC')}",
                    ParagraphStyle('RightDate', parent=self.caption_style, alignment=2),
                ),
            ],
        ]

        t = Table(header_data, colWidths=[330, 174])
        t.setStyle(
            TableStyle(
                [
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 1),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ]
            )
        )
        items.append(t)
        items.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F172A"), spaceAfter=6))
        return items

    def _build_metadata_section(self, inspection: Inspection, summary: dict[str, Any]) -> list[Any]:
        items: list[Any] = []
        items.append(Paragraph("1. INSPECTION & PRODUCT METADATA", self.section_heading))

        prod = inspection.product
        prod_name = prod.name if prod else "Not specified"
        brand = prod.brand if prod and prod.brand else (prod.manufacturer if prod and prod.manufacturer else "N/A")
        category = prod.category if prod and prod.category else "General"
        barcode = inspection.barcode_or_qr or "Not provided"

        catalog_version = summary.get('catalog_version') or '1.0.0'
        catalog_hash = summary.get('catalog_hash') or 'B847E70C09BF2666CEE117F0B800B8F26DE5D5D86059D70966D794A5E6E13ADC'
        hash_disp = f"{catalog_hash[:28]}..." if len(catalog_hash) > 28 else catalog_hash
        rule_date = summary.get('inspection_date') or (
            inspection.created_at.strftime('%Y-%m-%d') if inspection.created_at else 'Current'
        )

        table_data = [
            [
                Paragraph("<b>Product Name:</b>", self.body_style),
                Paragraph(prod_name, self.body_style),
                Paragraph("<b>Inspection Date:</b>", self.body_style),
                Paragraph(rule_date, self.body_style),
            ],
            [
                Paragraph("<b>Brand / Mfr:</b>", self.body_style),
                Paragraph(brand, self.body_style),
                Paragraph("<b>Barcode / QR:</b>", self.body_style),
                Paragraph(barcode, self.body_style),
            ],
            [
                Paragraph("<b>Commodity Category:</b>", self.body_style),
                Paragraph(category.capitalize(), self.body_style),
                Paragraph("<b>Rule Catalog Ver:</b>", self.body_style),
                Paragraph(f"v{catalog_version}", self.body_style),
            ],
            [
                Paragraph("<b>Catalog SHA-256:</b>", self.body_style),
                Paragraph(f"<font size=6.5 fontName=Courier>{hash_disp}</font>", self.body_style),
                Paragraph("<b>Inspection Notes:</b>", self.body_style),
                Paragraph(inspection.notes or "None recorded", self.body_style),
            ],
        ]

        t = Table(table_data, colWidths=[110, 142, 110, 142])
        t.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                    ('TOPPADDING', (0, 0), (-1, -1), 3.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
            )
        )
        items.append(t)
        return items

    def _build_compliance_summary_section(self, summary: dict[str, Any]) -> list[Any]:
        items: list[Any] = []
        items.append(Paragraph("2. EXECUTIVE COMPLIANCE SUMMARY", self.section_heading))

        eng = summary.get('engine_summary', {})
        insp = summary.get('inspector_summary', {})
        final = summary.get('final_result', {})

        overall_engine = eng.get('overall_result', 'PENDING_ANALYSIS')
        review_status = insp.get('review_status', 'NOT_STARTED')
        final_status = final.get('inspection_status', 'DRAFT')

        # Status badge colors
        eng_color = "#16A34A" if overall_engine == "COMPLIANT" else ("#DC2626" if overall_engine == "POTENTIAL_VIOLATIONS_DETECTED" else "#D97706")
        rev_color = "#16A34A" if review_status == "COMPLETE" else "#D97706"

        banner_data = [
            [
                Paragraph("<b>DETERMINISTIC ENGINE RESULT</b>", self.caption_style),
                Paragraph("<b>INSPECTOR REVIEW STATUS</b>", self.caption_style),
                Paragraph("<b>FINAL INSPECTION STATUS</b>", self.caption_style),
            ],
            [
                Paragraph(f"<b><font color='{eng_color}' size=10>{overall_engine.replace('_', ' ')}</font></b>", self.body_style),
                Paragraph(f"<b><font color='{rev_color}' size=10>{review_status.replace('_', ' ')}</font></b>", self.body_style),
                Paragraph(f"<b><font size=10>{final_status}</font></b>", self.body_style),
            ],
        ]

        t_banner = Table(banner_data, colWidths=[168, 168, 168])
        t_banner.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ]
            )
        )
        items.append(t_banner)
        items.append(Spacer(1, 4))

        # Metrics Breakdown
        total = eng.get('total_checks', 0)
        passed = eng.get('passed', 0)
        violations = eng.get('potential_violations', 0)
        warnings = eng.get('warnings', 0)
        manual = eng.get('manual_review', 0)
        not_app = eng.get('not_applicable', 0)

        reviewed_count = insp.get('reviewed_count', 0)
        confirmed_count = insp.get('confirmed_count', 0)
        rejected_count = insp.get('rejected_count', 0)
        insp_manual = insp.get('manual_review_count', 0)

        sev = eng.get('severity_distribution', {})
        crit = sev.get('critical', 0)
        maj = sev.get('major', 0)

        metrics_data = [
            [
                Paragraph("<b>Automated Checks:</b>", self.body_bold),
                Paragraph(f"Total Evaluated: <b>{total}</b>", self.body_style),
                Paragraph(f"Passed: <font color='#16A34A'><b>{passed}</b></font>", self.body_style),
                Paragraph(f"Violations: <font color='#DC2626'><b>{violations}</b></font>", self.body_style),
                Paragraph(f"Warnings/Manual: <font color='#D97706'><b>{warnings + manual}</b></font>", self.body_style),
                Paragraph(f"Exempt / NA: <b>{not_app}</b>", self.body_style),
            ],
            [
                Paragraph("<b>Inspector Actions:</b>", self.body_bold),
                Paragraph(f"Total Reviewed: <b>{reviewed_count}</b>", self.body_style),
                Paragraph(f"Confirmed: <font color='#16A34A'><b>{confirmed_count}</b></font>", self.body_style),
                Paragraph(f"Rejected: <b>{rejected_count}</b>", self.body_style),
                Paragraph(f"Manual Escalated: <b>{insp_manual}</b>", self.body_style),
                Paragraph(f"Critical / Major: <b>{crit}/{maj}</b>", self.body_style),
            ],
        ]

        t_metrics = Table(metrics_data, colWidths=[90, 82, 75, 85, 95, 77])
        t_metrics.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
            )
        )
        items.append(t_metrics)
        return items

    def _build_findings_section(
        self,
        findings: list[Finding],
        storage_base_path: str | Path | None,
    ) -> list[Any]:
        items: list[Any] = []
        items.append(Paragraph(f"3. STATUTORY FINDINGS & EVIDENCE AUDIT ({len(findings)} Records)", self.section_heading))

        if not findings:
            empty_table = Table(
                [[Paragraph("<i>No statutory non-compliances, warnings, or manual verification items detected. All evaluated mandatory declarations are compliant or not applicable.</i>", self.body_style)]],
                colWidths=[504],
            )
            empty_table.setStyle(
                TableStyle(
                    [
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#BBF7D0')),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ]
                )
            )
            items.append(empty_table)
            return items

        for index, finding in enumerate(findings, start=1):
            finding_flowables = self._build_single_finding_block(index, finding, storage_base_path)
            items.append(KeepTogether(finding_flowables))
            items.append(Spacer(1, 6))

        return items

    def _build_single_finding_block(
        self,
        index: int,
        finding: Finding,
        storage_base_path: str | Path | None,
    ) -> list[Any]:
        block: list[Any] = []

        rule_id = finding.rule_check_id or "RULE"
        title = finding.title or "Finding"
        citation = finding.legal_citation or "Legal Metrology (Packaged Commodities) Rules, 2011"
        severity = (finding.severity or "warning").upper()
        engine_status = finding.status or "open"

        # Inspector decision details
        decision = (finding.inspector_decision or "PENDING").upper()
        reviewer = finding.reviewer_name or "Unassigned"
        review_time = finding.reviewed_at.strftime('%Y-%m-%d %H:%M') if finding.reviewed_at else "Pending"
        notes = finding.inspector_notes or "No notes provided"

        # Colors
        badge_color = "#16A34A" if severity == "PASS" else ("#DC2626" if severity in ("CRITICAL", "MAJOR") else "#D97706")
        dec_color = "#16A34A" if decision == "CONFIRM" else ("#DC2626" if decision == "REJECT" else "#D97706")

        # Top Header Bar
        header_row = [
            [
                Paragraph(f"<b>#{index}. {rule_id} — {title}</b>", self.body_bold),
                Paragraph(f"<b><font color='{badge_color}'>{severity}</font></b> | Engine: <b>{engine_status.upper()}</b>", ParagraphStyle('SevR', parent=self.body_style, alignment=2)),
            ]
        ]
        t_head = Table(header_row, colWidths=[360, 144])
        t_head.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ]
            )
        )
        block.append(t_head)

        # Evidence Image preparation
        annotated_img_flowable = self._create_annotated_image_flowable(finding, storage_base_path)

        # Body details
        detected = finding.detected_value or "None detected"
        expected = finding.expected_condition or "Mandatory declaration pursuant to statute"
        what = finding.what or finding.description or "N/A"
        why = finding.why or "Statutory requirement under Legal Metrology Rules, 2011"
        snippet = finding.evidence_snippet or "N/A"
        confidence = f"{(finding.ocr_confidence * 100):.1f}%" if finding.ocr_confidence is not None else "N/A"
        source_file = finding.source_image or "Package Image"

        details_data = [
            [
                Paragraph("<b>Legal Citation:</b>", self.body_bold),
                Paragraph(citation, self.statutory_citation),
            ],
            [
                Paragraph("<b>Detected Value:</b>", self.body_bold),
                Paragraph(f"<font color='#0F172A'><b>{detected}</b></font> (Expected: {expected})", self.body_style),
            ],
            [
                Paragraph("<b>Explanation (WHAT):</b>", self.body_bold),
                Paragraph(what, self.body_style),
            ],
            [
                Paragraph("<b>Statutory Reason (WHY):</b>", self.body_bold),
                Paragraph(why, self.body_style),
            ],
            [
                Paragraph("<b>Evidence Traceability:</b>", self.body_bold),
                Paragraph(
                    f"Source: <b>{source_file}</b> | OCR Snippet: &ldquo;<b>{snippet}</b>&rdquo; | Conf: <b>{confidence}</b>",
                    self.body_style,
                ),
            ],
            [
                Paragraph("<b>Inspector Audit Decision:</b>", self.body_bold),
                Paragraph(
                    f"Decision: <b><font color='{dec_color}'>{decision}</font></b> | Reviewer: <b>{reviewer}</b> ({review_time})<br/>"
                    f"Notes: <i>{notes}</i>",
                    self.body_style,
                ),
            ],
        ]

        if annotated_img_flowable:
            # Layout with thumbnail on the right
            details_table = Table(details_data, colWidths=[105, 255])
            details_table.setStyle(
                TableStyle(
                    [
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ]
                )
            )
            side_by_side = Table(
                [[details_table, annotated_img_flowable]],
                colWidths=[365, 139],
            )
            side_by_side.setStyle(
                TableStyle(
                    [
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ]
                )
            )
            block.append(side_by_side)
        else:
            # Full-width table
            details_table = Table(details_data, colWidths=[110, 394])
            details_table.setStyle(
                TableStyle(
                    [
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ]
                )
            )
            block.append(details_table)

        return block

    def _create_annotated_image_flowable(
        self,
        finding: Finding,
        storage_base_path: str | Path | None,
    ) -> Image | None:
        """Annotates the source image with the finding's bounding box and returns a ReportLab Image."""
        # Locate image file
        img_path = self._resolve_image_disk_path(finding, storage_base_path)
        if not img_path or not os.path.exists(img_path):
            return None

        try:
            with PILImage.open(img_path) as pil_img:
                pil_img = pil_img.convert("RGB")
                draw = ImageDraw.Draw(pil_img)

                loc = finding.evidence_location
                if loc and isinstance(loc, list) and len(loc) >= 4:
                    # Polygon coordinates [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                    pts: list[tuple[float, float]] = []
                    for pt in loc:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            pts.append((float(pt[0]), float(pt[1])))

                    if len(pts) >= 4:
                        # Draw bounding polygon
                        draw.polygon(pts, outline="#DC2626", width=4)

                # Resize to thumbnail (max width 130 pt, max height 95 pt)
                orig_w, orig_h = pil_img.size
                target_w = 130
                target_h = int(orig_h * (target_w / orig_w)) if orig_w > 0 else 95
                if target_h > 95:
                    target_h = 95
                    target_w = int(orig_w * (target_h / orig_h)) if orig_h > 0 else 130

                thumb = pil_img.resize((target_w * 2, target_h * 2), PILImage.Resampling.LANCZOS)
                img_io = io.BytesIO()
                thumb.save(img_io, format="JPEG", quality=85)
                img_io.seek(0)

                return Image(img_io, width=target_w, height=target_h)
        except Exception:
            return None

    def _resolve_image_disk_path(
        self,
        finding: Finding,
        storage_base_path: str | Path | None,
    ) -> str | None:
        base = Path(storage_base_path) if storage_base_path else Path("storage")

        # 1. Check direct storage_path property
        if finding.storage_path:
            p = Path(finding.storage_path)
            if p.is_file():
                return str(p)
            combined = base / p.name
            if combined.is_file():
                return str(combined)

        # 2. Check source_image in storage uploads
        if finding.source_image:
            candidates = [
                base / "uploads" / finding.source_image,
                base / finding.source_image,
                Path("storage/uploads") / finding.source_image,
                Path("tests/fixtures") / finding.source_image,
            ]
            for c in candidates:
                if c.is_file():
                    return str(c)

        return None

    def _build_legal_disclaimer(self, summary: dict[str, Any]) -> list[Any]:
        items: list[Any] = []
        items.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=4))
        items.append(Paragraph("4. STATUTORY NOTICE & LEGAL DISCLAIMER", self.section_heading))

        catalog_hash = summary.get('catalog_hash') or 'B847E70C09BF2666CEE117F0B800B8F26DE5D5D86059D70966D794A5E6E13ADC'
        disclaimer_text = (
            "<b>STATUTORY NOTICE:</b> This inspection report is generated using PRAMAN's AI-assisted automated optical inspection "
            "and deterministic rule evaluation engine. Rule evaluations are strictly derived from the codified Legal Metrology "
            "(Packaged Commodities) Rules, 2011 (Catalog v1.0.0, SHA-256: "
            f"<code>{catalog_hash[:20]}...</code>).<br/>"
            "<b>LEGAL AUTHORITY:</b> PRAMAN is an inspection support tool and does not constitute a judicial authority, court order, "
            "or legal adjudication. Final statutory determinations, notices, compounding orders, and seizure actions reside exclusively "
            "with authorized Legal Metrology Officers under the Legal Metrology Act, 2009.<br/>"
            "<b>MANUAL REVIEW SAFEGUARD:</b> Any check marked for manual review reflects visual, dimension, or temporal declarations "
            "requiring physical verification and is never certified as compliant without designated inspector resolution."
        )

        t = Table([[Paragraph(disclaimer_text, self.disclaimer_style)]], colWidths=[504])
        t.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]
            )
        )
        items.append(t)
        return items
