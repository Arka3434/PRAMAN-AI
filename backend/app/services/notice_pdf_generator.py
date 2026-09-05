from __future__ import annotations

import io
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

from app.models.notice import Notice


class NumberedNoticeCanvas(canvas.Canvas):
    """Custom canvas that tracks total pages and draws running headers, footers, and draft watermarks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs['pageCompression'] = 0
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []
        self._is_draft: bool = True

    def set_draft(self, is_draft: bool) -> None:
        self._is_draft = is_draft

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(page_count)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count: int) -> None:
        self.saveState()

        # 1. Draft Watermark (Only if draft / reviewed, omitted once issued)
        if self._is_draft:
            self.saveState()
            self.setFont("Helvetica-Bold", 34)
            # Reddish translucent watermark
            self.setFillColor(colors.Color(0.85, 0.15, 0.15, alpha=0.14))
            self.translate(306, 420)
            self.rotate(42)
            self.drawCentredString(0, 0, "DRAFT — FOR OFFICER REVIEW ONLY")
            self.restoreState()

        # 2. Running Header (Pages > 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#1E293B"))
            self.drawString(54, 752, "LEGAL METROLOGY ENFORCEMENT — STATUTORY NOTICE DRAFT")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawRightString(558, 752, "Confidential / Statutory Enforcement")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 746, 558, 746)

        # 3. Running Footer (All pages)
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(54, 32, "PRAMAN AI • Legal Metrology Act, 2009 & PCR 2011 Administrative System")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 42, 558, 42)

        self.restoreState()


class NoticePdfGenerator:
    """Generates official statutory notice drafts and inspection memos adhering to legal metrology guardrails."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._init_styles()

    def _init_styles(self) -> None:
        self.title_style = ParagraphStyle(
            'NoticeTitle',
            parent=self.styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=19,
            alignment=1,  # Centered
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=2,
        )
        self.subtitle_style = ParagraphStyle(
            'NoticeSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=14,
            alignment=1,  # Centered
            textColor=colors.HexColor('#334155'),
            spaceAfter=6,
        )
        self.status_badge_style = ParagraphStyle(
            'StatusBadge',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            alignment=1,
            textColor=colors.HexColor('#B91C1C'),
            spaceAfter=10,
        )
        self.section_header = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=6,
            spaceAfter=4,
        )
        self.body_style = ParagraphStyle(
            'Body',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#1E293B'),
        )
        self.body_bold = ParagraphStyle(
            'BodyBold',
            parent=self.body_style,
            fontName='Helvetica-Bold',
        )
        self.legal_text = ParagraphStyle(
            'LegalText',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11.5,
            textColor=colors.HexColor('#334155'),
            alignment=4,  # Justified
        )
        self.disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=self.styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            leading=10.5,
            textColor=colors.HexColor('#64748B'),
            alignment=4,
        )

    def generate_pdf(self, notice: Notice, storage_base_path: Path | None = None) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
            pageCompression=0,
        )


        elements: list[Any] = []
        is_draft = (notice.status != 'ISSUED_BY_OFFICER')

        # 1. Header Banner
        doc_header = "STATUTORY SHOW-CAUSE NOTICE DRAFT / INSPECTION MEMO" if is_draft else "STATUTORY SHOW-CAUSE NOTICE"
        elements.append(Paragraph("GOVERNMENT OF LEGAL METROLOGY ENFORCEMENT", self.subtitle_style))
        elements.append(Paragraph(doc_header, self.title_style))
        elements.append(Paragraph("Issued under Section 15 of the Legal Metrology Act, 2009", self.subtitle_style))

        status_text = f"DOCUMENT STATUS: {notice.status.replace('_', ' ').upper()}"
        if is_draft:
            status_text += " — (NOT A COURT ORDER / FOR OFFICER REVIEW ONLY)"
        elements.append(Paragraph(status_text, self.status_badge_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0F172A'), spaceAfter=8))

        # 2. Reference & Date Metadata Table
        created_str = notice.created_at.strftime('%d-%b-%Y %H:%M UTC') if notice.created_at else 'N/A'
        issued_str = notice.issued_at.strftime('%d-%b-%Y %H:%M UTC') if notice.issued_at else 'Pending Issuance'
        meta_data = [
            [
                Paragraph("<b>Notice Reference:</b>", self.body_style),
                Paragraph(f"<b>{notice.notice_reference}</b>", self.body_style),
                Paragraph("<b>Inspection Date:</b>", self.body_style),
                Paragraph(created_str, self.body_style),
            ],
            [
                Paragraph("<b>Inspection Ref:</b>", self.body_style),
                Paragraph(f"INSP-{notice.inspection_id[:8]}", self.body_style),
                Paragraph("<b>Date of Issuance:</b>", self.body_style),
                Paragraph(issued_str, self.body_style),
            ],
            [
                Paragraph("<b>Catalog Version:</b>", self.body_style),
                Paragraph(str(notice.legal_version_context.get('catalog_version', '1.0.0')), self.body_style),
                Paragraph("<b>Catalog SHA-256:</b>", self.body_style),
                Paragraph(f"<font size=6>{str(notice.legal_version_context.get('catalog_sha256', ''))[:24]}...</font>", self.body_style),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[90, 162, 90, 162])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 8))

        # 3. Addressee & Premise Information
        elements.append(Paragraph("ADDRESSEE & PREMISES DETAILS", self.section_header))
        addressee_data = [
            [
                Paragraph("<b>To / Recipient:</b>", self.body_style),
                Paragraph(f"<b>{notice.recipient_name}</b>", self.body_style),
            ],
            [
                Paragraph("<b>Legal Role / Capacity:</b>", self.body_style),
                Paragraph(f"{notice.recipient_role.replace('_', ' ').title()}", self.body_style),
            ],
            [
                Paragraph("<b>Establishment Inspected:</b>", self.body_style),
                Paragraph(f"{notice.establishment_name or 'Commercial Establishment'}", self.body_style),
            ],
            [
                Paragraph("<b>Registered / Physical Address:</b>", self.body_style),
                Paragraph(f"{notice.recipient_address}", self.body_style),
            ],
            [
                Paragraph("<b>Venue of Inspection:</b>", self.body_style),
                Paragraph(f"{notice.inspection_venue or 'Retail / Commercial Premises'}", self.body_style),
            ],
        ]
        addressee_table = Table(addressee_data, colWidths=[140, 364])
        addressee_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#F1F5F9')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(addressee_table)
        elements.append(Spacer(1, 8))

        # 4. Preamble
        snapshot = notice.inspection_snapshot or {}
        prod_name = snapshot.get('product_name') or 'Pre-Packaged Commodity'
        preamble_text = (
            f"<b>WHEREAS</b>, an inspection under Section 15 of the Legal Metrology Act, 2009 was carried out "
            f"in respect of the pre-packaged commodity declared as <b>{prod_name}</b> at the venue specified above; "
            f"<br/><br/>"
            f"<b>AND WHEREAS</b>, examination and multi-panel package scrutiny of the commodity revealed prima facie "
            f"contraventions of the Legal Metrology (Packaged Commodities) Rules, 2011, punishable under the substantive "
            f"penal provisions of the Legal Metrology Act, 2009 as detailed in the Schedule of Statutory Charges below:"
        )
        elements.append(Paragraph(preamble_text, self.legal_text))
        elements.append(Spacer(1, 8))

        # 5. Table of Statutory Charges
        elements.append(Paragraph("SCHEDULE OF STATUTORY CHARGES", self.section_header))
        charges_data = [
            [
                Paragraph("<b>#</b>", self.body_style),
                Paragraph("<b>Rule & Legal Citation</b>", self.body_style),
                Paragraph("<b>Factual Non-Conformity Observed</b>", self.body_style),
                Paragraph("<b>Substantive Governing Section</b>", self.body_style),
                Paragraph("<b>Review Status</b>", self.body_style),
            ]
        ]

        charges = notice.statutory_charges or []
        for idx, ch in enumerate(charges, 1):
            is_manual = ch.get('requires_manual_review', False)
            status_badge = "<font color='#B91C1C'><b>MANUAL REVIEW</b></font>" if is_manual else "<font color='#16A34A'><b>STATUTORY MAPPED</b></font>"
            charges_data.append([
                Paragraph(str(idx), self.body_style),
                Paragraph(f"<b>{ch.get('rule_id', '')}</b><br/><font size=7 color='#475569'>{ch.get('rule_citation', '')}</font>", self.body_style),
                Paragraph(ch.get('defect_description', ''), self.body_style),
                Paragraph(f"<font size=7.5><b>{ch.get('statutory_provision', '')}</b><br/><font color='#64748B'>{ch.get('liability_basis', '')}</font></font>", self.body_style),
                Paragraph(status_badge, self.body_style),
            ])

        charges_table = Table(charges_data, colWidths=[20, 115, 145, 150, 74])
        charges_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(charges_table)
        elements.append(Spacer(1, 8))

        # 6. Procedural Direction to Show Cause
        elements.append(Paragraph("DIRECTION TO SHOW CAUSE & PROCEDURAL TIMELINE", self.section_header))
        resp_days = notice.response_period_days or 15
        resp_basis = notice.response_period_basis or "Configurable administrative show-cause period (Draft convenience; officer-confirmed procedural term)"
        show_cause_text = (
            f"<b>NOW THEREFORE</b>, you are hereby called upon to show cause in writing within <b>{resp_days} days</b> "
            f"from the receipt of this notice, explaining why penal action should not be initiated against you under the "
            f"applicable sections of the Legal Metrology Act, 2009 for the violations listed above.<br/><br/>"
            f"<b>Procedural Term Basis:</b> {resp_basis}<br/>"
            f"<i>Important Statutory Clarification:</i> The response timeline of {resp_days} days is an administrative "
            f"show-cause term configured and verified by the issuing officer, and does not represent an inflexible or automated statutory mandate."
        )
        elements.append(Paragraph(show_cause_text, self.legal_text))
        elements.append(Spacer(1, 8))

        # 7. Compounding Clause (Optional / Configured)
        if notice.compounding_clause_included:
            elements.append(Paragraph("COMPOUNDING OF OFFENSE UNDER SECTION 48", self.section_header))
            compounding_text = (
                "<b>ADVISEMENT PURSUANT TO SECTION 48 OF THE LEGAL METROLOGY ACT, 2009:</b><br/>"
                "The recipient is hereby informed that any offense punishable under Section 36(1) may, either before or after "
                "the institution of prosecution, be compounded by the Director or Controller or authorized Legal Metrology Officer "
                "on payment of such sum as may be prescribed, provided that no similar offense has been compounded within the "
                "preceding three years. If eligible and desirous of compounding the alleged offense without court proceedings, "
                "you may submit a formal written application within the stipulated response period."
            )
            elements.append(Paragraph(compounding_text, self.legal_text))
            elements.append(Spacer(1, 8))

        # 8. Evidence Annexure
        elements.append(Paragraph("ANNEXURE: MULTI-PANEL EVIDENCE RECORD", self.section_header))
        evidence_data = [
            [
                Paragraph("<b>Panel</b>", self.body_style),
                Paragraph("<b>Original File</b>", self.body_style),
                Paragraph("<b>Image Reference / SHA-256 Digest</b>", self.body_style),
            ]
        ]
        evidence_refs = notice.evidence_references or []
        for ev in evidence_refs:
            panel = ev.get('panel_type', 'primary').upper()
            fname = ev.get('file_name', 'evidence.jpg')
            img_id = ev.get('image_id', '')
            sha = ev.get('sha256', '')
            evidence_data.append([
                Paragraph(panel, self.body_style),
                Paragraph(fname, self.body_style),
                Paragraph(f"<font size=7>ID: {img_id}<br/>SHA-256: {sha}</font>", self.body_style),
            ])

        ev_table = Table(evidence_data, colWidths=[70, 150, 284])
        ev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(ev_table)
        elements.append(Spacer(1, 14))

        # 9. Officer Attestation & Signature Block
        elements.append(KeepTogether([
            Paragraph("OFFICER ATTESTATION & SIGNATURE", self.section_header),
            Spacer(1, 4),
            Table([
                [
                    Paragraph(
                        "<b>Inspecting & Authorized Officer:</b><br/>"
                        f"Name: <b>{notice.officer_name or 'PENDING OFFICER SIGNATURE'}</b><br/>"
                        f"Designation: {notice.officer_designation or 'Legal Metrology Inspector'}<br/>"
                        f"Jurisdiction / Office: {notice.officer_office or 'Legal Metrology Department'}<br/>"
                        f"Issuance Date: {notice.issued_at.strftime('%d-%b-%Y') if notice.issued_at else 'UNISSUED DRAFT'}",
                        self.body_style,
                    ),
                    Paragraph(
                        "<br/><br/><br/>"
                        "__________________________________________<br/>"
                        "<b>Signature & Official Seal of Authorized Officer</b><br/>"
                        "<font size=7 color='#64748B'>Legal Metrology Enforcement Branch</font>",
                        self.body_style,
                    ),
                ]
            ], colWidths=[250, 254], style=[
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]),
            Spacer(1, 8),
            Paragraph(
                "<b>MANDATORY STATUTORY DISCLAIMER:</b> This document is an assistive statutory notice draft / "
                "inspection memo generated for the verification and action of the authorized Legal Metrology Officer. "
                "It is not an automated judicial judgment, conviction, or court order. The inspecting officer remains "
                "fully responsible for reviewing, certifying, and legally issuing this notice under their statutory authority.",
                self.disclaimer_style,
            )
        ]))

        def make_canvas(*args: Any, **kwargs: Any) -> NumberedNoticeCanvas:
            canv = NumberedNoticeCanvas(*args, **kwargs)
            canv.set_draft(is_draft)
            return canv

        doc.build(elements, canvasmaker=make_canvas)
        return buffer.getvalue()


notice_pdf_generator = NoticePdfGenerator()
