"""Deterministic Compliance Rules Engine for PRAMAN AI.

Evaluates pre-packaged goods inspection evidence against the versioned
statutory provisions defined in legal/rule_catalog/rules_v1.json.

Design specifications:
- Pure, framework-independent Python domain service.
- Strict catalog integrity verification via SHA-256 digest.
- Execution guardrails: SAFE rules execute deterministically;
  NEEDS_VERIFICATION rules never produce automated violations.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

EvaluationStatus = Literal[
    'PASS',
    'POTENTIAL_VIOLATION',
    'WARNING',
    'MANUAL_REVIEW',
    'NOT_APPLICABLE',
]

RuleSeverity = Literal['critical', 'major', 'warning', 'info']


def parse_iso_date(value: Any) -> date:
    """Parse string, date, or datetime into a date object."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        clean = value.strip()
        m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})', clean)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(year, month, day)
        raise ValueError(f"Unrecognized date format: '{value}'. Expected YYYY-MM-DD or ISO timestamp.")
    raise TypeError(f"Cannot parse date from {type(value).__name__}: {value}")


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    title: str
    legal_citation: str
    source_document: str
    effective_from: str
    effective_to: str | None
    applicability: str
    exemptions: list[str]
    input_fields: list[str]
    check_type: str
    expected_condition: str
    severity: str
    executable_status: str
    evidence_requirement: str

    def is_effective(self, on_date: date | datetime | str) -> bool:
        """Determine if this rule is in effect on the specified date."""
        target_dt = parse_iso_date(on_date)
        from_dt = parse_iso_date(self.effective_from)
        if target_dt < from_dt:
            return False
        if self.effective_to is not None:
            to_dt = parse_iso_date(self.effective_to)
            if target_dt > to_dt:
                return False
        return True


@dataclass
class InspectionEvaluationContext:
    inspection_id: str
    inspection_context: dict[str, Any] = field(default_factory=dict)
    structured_declarations: dict[str, Any] = field(default_factory=dict)
    ocr_evidence: dict[str, Any] = field(default_factory=dict)
    inspection_date: str | date | datetime | None = None


@dataclass
class RuleEvaluation:
    rule_id: str
    title: str
    legal_citation: str
    status: EvaluationStatus
    severity: str
    detected_value: str | None
    expected_condition: str
    reason: str
    evidence_references: list[str] = field(default_factory=list)
    executable_status: str = 'SAFE'
    what: str = ''
    why: str = ''
    evidence_snippet: str | None = None
    evidence_location: list[Any] | None = None
    ocr_confidence: float | None = None
    source_image: str | None = None
    catalog_version: str = ''
    catalog_hash: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComplianceEvaluationReport:
    evaluation_id: str
    inspection_id: str
    catalog_version: str
    catalog_hash: str
    evaluated_at: str
    summary: dict[str, int]
    evaluations: list[RuleEvaluation]
    inspection_date: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'evaluation_id': self.evaluation_id,
            'inspection_id': self.inspection_id,
            'catalog_version': self.catalog_version,
            'catalog_hash': self.catalog_hash,
            'inspection_date': self.inspection_date,
            'evaluated_at': self.evaluated_at,
            'summary': self.summary,
            'evaluations': [e.to_dict() for e in self.evaluations],
        }

    def to_findings_projection(self) -> list[dict[str, Any]]:
        """Project evaluations into a format directly compatible with the Finding model."""
        projections: list[dict[str, Any]] = []
        for ev in self.evaluations:
            if ev.status == 'NOT_APPLICABLE':
                continue

            if ev.status == 'PASS':
                finding_status = 'resolved'
                severity = 'pass'
                title = f'{ev.rule_id}: Statutory declaration verified'
            elif ev.status == 'POTENTIAL_VIOLATION':
                finding_status = 'open'
                severity = ev.severity
                title = f'{ev.rule_id}: Potential statutory violation'
            elif ev.status == 'WARNING':
                finding_status = 'open'
                severity = 'warning'
                title = f'{ev.rule_id}: Statutory warning'
            else:  # MANUAL_REVIEW
                finding_status = 'open'
                severity = 'warning'
                title = f'{ev.rule_id}: Manual verification required'

            source_img = ev.source_image or (ev.evidence_references[-1] if ev.evidence_references else None)
            evidence_data = {
                'source_image': source_img,
                'source_file': source_img,
                'evidence_snippet': ev.evidence_snippet,
                'evidence_location': ev.evidence_location,
                'ocr_confidence': ev.ocr_confidence,
                'catalog_version': self.catalog_version,
                'catalog_hash': self.catalog_hash,
                'inspection_date': self.inspection_date,
                'rule_status': ev.status,
            }
            evidence_ref = json.dumps(evidence_data)

            projections.append(
                {
                    'inspection_id': self.inspection_id,
                    'severity': severity,
                    'status': finding_status,
                    'title': title,
                    'description': ev.reason,
                    'detected_value': ev.detected_value,
                    'rule_check_id': ev.rule_id,
                    'evidence_reference': evidence_ref,
                    'rule_status': ev.status,
                    'what': ev.what or ev.reason,
                    'why': ev.why or f"{ev.legal_citation}. Expected: {ev.expected_condition}",
                    'legal_citation': ev.legal_citation,
                    'expected_condition': ev.expected_condition,
                    'source_image': source_img,
                    'evidence_snippet': ev.evidence_snippet,
                    'evidence_location': ev.evidence_location,
                    'ocr_confidence': ev.ocr_confidence,
                    'catalog_version': self.catalog_version,
                    'catalog_hash': self.catalog_hash,
                }
            )
        return projections


class ComplianceEngine:
    """Deterministic, catalog-driven compliance rules engine."""

    # Standard approved metric and count units under Legal Metrology Rules
    APPROVED_UNITS = {
        'g',
        'gram',
        'grams',
        'gm',
        'gms',
        'kg',
        'kilogram',
        'kilograms',
        'mg',
        'milligram',
        'l',
        'litre',
        'litres',
        'liter',
        'liters',
        'ml',
        'millilitre',
        'millilitres',
        'm',
        'metre',
        'metres',
        'cm',
        'centimetre',
        'centimetres',
        'mm',
        'millimetre',
        'n',
        'u',
        'number',
        'numbers',
        'piece',
        'pieces',
        'pcs',
        'count',
        'units',
        'pack',
        'packs',
        'packets',
        'bottles',
        'tablets',
        'capsules',
    }

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        if catalog_path is None:
            # Default to legal/rule_catalog/rules_v1.json relative to repository root
            catalog_path = (
                Path(__file__).resolve().parents[3]
                / 'legal'
                / 'rule_catalog'
                / 'rules_v1.json'
            )
        self.catalog_path = Path(catalog_path)
        self.catalog_version: str = ''
        self.catalog_hash: str = ''
        self.rules: dict[str, RuleDefinition] = {}
        self._load_and_validate_catalog()

    def _load_and_validate_catalog(self) -> None:
        if not self.catalog_path.exists():
            raise FileNotFoundError(
                f'Rule catalog not found at: {self.catalog_path}'
            )

        content = self.catalog_path.read_bytes()
        self.catalog_hash = hashlib.sha256(content).hexdigest()

        try:
            data = json.loads(content.decode('utf-8'))
        except Exception as exc:
            raise ValueError(f'Invalid JSON in rule catalog: {exc}') from exc

        self.catalog_version = data.get('catalog_version', 'unknown')
        raw_rules = data.get('rules', [])
        if not raw_rules:
            raise ValueError('Rule catalog contains no rules.')

        mandatory_fields = {
            'rule_id',
            'title',
            'legal_citation',
            'source_document',
            'effective_from',
            'effective_to',
            'applicability',
            'exemptions',
            'input_fields',
            'check_type',
            'expected_condition',
            'severity',
            'executable_status',
            'evidence_requirement',
        }

        parsed_rules: dict[str, RuleDefinition] = {}
        for r in raw_rules:
            missing = mandatory_fields - set(r.keys())
            if missing:
                raise ValueError(
                    f"Rule {r.get('rule_id')} missing fields: {missing}"
                )

            rule_def = RuleDefinition(
                rule_id=str(r['rule_id']),
                title=str(r['title']),
                legal_citation=str(r['legal_citation']),
                source_document=str(r['source_document']),
                effective_from=str(r['effective_from']),
                effective_to=r['effective_to'],
                applicability=str(r['applicability']),
                exemptions=list(r['exemptions']),
                input_fields=list(r['input_fields']),
                check_type=str(r['check_type']),
                expected_condition=str(r['expected_condition']),
                severity=str(r['severity']),
                executable_status=str(r['executable_status']),
                evidence_requirement=str(r['evidence_requirement']),
            )
            parsed_rules[rule_def.rule_id] = rule_def

        # Order canonically by rule_id
        self.rules = dict(sorted(parsed_rules.items()))

    @staticmethod
    def _is_empty_or_none(value: Any) -> bool:
        if value is None:
            return True
        val_str = str(value).strip().lower()
        return val_str in {'', 'none', 'null', 'not provided', 'undefined'}

    @staticmethod
    def _find_best_ocr_region(
        ocr_regions: list[dict[str, Any]],
        candidates: list[str | None],
    ) -> dict[str, Any] | None:
        """Find the region that best matches candidate strings with priority weighting."""
        if not ocr_regions:
            return None
        valid_candidates = [
            str(c).strip().lower() for c in candidates if c and str(c).strip()
        ]
        if not valid_candidates:
            return None

        best_region: dict[str, Any] | None = None
        best_score = 0

        for cand_idx, cand in enumerate(valid_candidates):
            priority_weight = (len(valid_candidates) - cand_idx) * 100
            for region in ocr_regions:
                reg_text = str(region.get('text', '')).strip().lower()
                if not reg_text:
                    continue
                score = 0
                if cand == reg_text:
                    score = 3000 + priority_weight
                elif cand in reg_text:
                    score = 2000 + len(cand) * 10 + priority_weight
                elif reg_text in cand and len(reg_text) >= 4:
                    score = 1000 + len(reg_text) * 10 + priority_weight
                else:
                    cand_tokens = set(re.findall(r'\w+', cand))
                    reg_tokens = set(re.findall(r'\w+', reg_text))
                    overlap = len(cand_tokens & reg_tokens)
                    if overlap >= 2:
                        score = overlap * 50 + priority_weight
                if score > best_score:
                    best_score = score
                    best_region = region
        return best_region

    @classmethod
    def _extract_evidence(
        cls,
        ocr_evidence: dict[str, Any],
        candidates: list[str | None],
        source_file: str,
    ) -> tuple[str | None, list[Any] | None, float | None, str]:
        """Extract matched text snippet, bounding box coordinates, confidence, and source image."""
        regions = ocr_evidence.get('ocr_regions', [])
        best = cls._find_best_ocr_region(regions, candidates)
        if best:
            snippet = best.get('text')
            bbox = best.get('bbox')
            conf = best.get('confidence')
            conf_float = round(float(conf), 4) if conf is not None else None
            return snippet, bbox, conf_float, source_file
        overall_conf = ocr_evidence.get('ocr_confidence')
        conf_float = (
            round(float(overall_conf), 4)
            if overall_conf is not None and float(overall_conf) > 0
            else None
        )
        return None, None, conf_float, source_file

    parse_date = staticmethod(parse_iso_date)

    def _resolve_inspection_date(self, context: InspectionEvaluationContext) -> date:
        """Resolve the effective date for the inspection evaluation."""
        if context.inspection_date is not None:
            return self.parse_date(context.inspection_date)
        ctx_date = context.inspection_context.get('inspection_date')
        if ctx_date is not None:
            return self.parse_date(ctx_date)
        ctx_created = context.inspection_context.get('created_at')
        if ctx_created is not None:
            return self.parse_date(ctx_created)
        return datetime.now(timezone.utc).date()

    def is_rule_effective(
        self, rule: RuleDefinition | str, on_date: date | datetime | str
    ) -> bool:
        """Check whether a rule is effective on a given date."""
        if isinstance(rule, str):
            if rule not in self.rules:
                raise KeyError(f"Rule ID '{rule}' not found in catalog.")
            rule_def = self.rules[rule]
        else:
            rule_def = rule
        return rule_def.is_effective(on_date)

    def get_active_rules(
        self, on_date: date | datetime | str
    ) -> list[RuleDefinition]:
        """Return all catalog rules effective on the given date in canonical order."""
        parsed_date = self.parse_date(on_date)
        return [r for r in self.rules.values() if r.is_effective(parsed_date)]

    def evaluate(
        self, context: InspectionEvaluationContext
    ) -> ComplianceEvaluationReport:
        """Deterministically evaluate an inspection against the loaded rule catalog."""
        evaluations: list[RuleEvaluation] = []
        summary = {
            'total_rules': len(self.rules),
            'passed': 0,
            'potential_violations': 0,
            'warnings': 0,
            'manual_review': 0,
            'not_applicable': 0,
        }

        ctx = context.inspection_context
        declarations = context.structured_declarations
        ocr_evidence = context.ocr_evidence
        source_file = (
            ocr_evidence.get('source_file')
            or declarations.get('source_file')
            or 'package_evidence'
        )

        effective_date = self._resolve_inspection_date(context)
        effective_date_str = effective_date.isoformat()

        # General Chapter II Rule 3 Filter (Industrial/Institutional or Bulk)
        consumer_type = str(ctx.get('consumer_type', 'retail')).lower()
        is_industrial_or_institutional = consumer_type in {
            'industrial',
            'institutional',
        }

        gross_qty = ctx.get('package_gross_quantity')
        gross_unit = str(ctx.get('package_quantity_unit', '')).lower()
        category = str(ctx.get('commodity_category', '')).lower()

        is_bulk_exempt = False
        if gross_qty is not None and gross_unit in {'kg', 'l', 'litre', 'liter'}:
            try:
                num_qty = float(gross_qty)
                # Exempt if > 25 kg/L unless cement/fertilizer/farm produce bags up to 50 kg
                if num_qty > 25.0 and category not in {
                    'cement',
                    'fertilizer',
                    'farm_produce',
                    'agricultural',
                }:
                    is_bulk_exempt = True
            except (ValueError, TypeError):
                pass

        # Evaluate rules sequentially in canonical order
        for rule_id, rule in self.rules.items():
            # 1. Temporal rule effectiveness check
            if not rule.is_effective(effective_date):
                parsed_from = self.parse_date(rule.effective_from)
                if effective_date < parsed_from:
                    reason = (
                        f"Rule {rule.rule_id} is not effective on inspection date "
                        f"{effective_date_str} (effective from {rule.effective_from})."
                    )
                    what = (
                        f"Not effective on inspection date {effective_date_str} "
                        f"(effective from {rule.effective_from})."
                    )
                    why = f"{rule.legal_citation}. Effective from {rule.effective_from}."
                else:
                    reason = (
                        f"Rule {rule.rule_id} is not effective on inspection date "
                        f"{effective_date_str} (expired on {rule.effective_to})."
                    )
                    what = (
                        f"Not effective on inspection date {effective_date_str} "
                        f"(expired on {rule.effective_to})."
                    )
                    why = f"{rule.legal_citation}. Effective until {rule.effective_to}."

                ev = RuleEvaluation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    legal_citation=rule.legal_citation,
                    status='NOT_APPLICABLE',
                    severity=rule.severity,
                    detected_value=None,
                    expected_condition=rule.expected_condition,
                    reason=reason,
                    evidence_references=[source_file],
                    executable_status=rule.executable_status,
                    what=what,
                    why=why,
                    source_image=source_file,
                    catalog_version=self.catalog_version,
                    catalog_hash=self.catalog_hash,
                )
                evaluations.append(ev)
                summary['not_applicable'] += 1
                continue

            # 2. General Chapter II exemptions
            if is_industrial_or_institutional:
                ev = RuleEvaluation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    legal_citation=rule.legal_citation,
                    status='NOT_APPLICABLE',
                    severity=rule.severity,
                    detected_value=None,
                    expected_condition=rule.expected_condition,
                    reason='Exempt under Rule 3(c): commodity packaged for industrial or institutional consumers.',
                    evidence_references=[source_file],
                    executable_status=rule.executable_status,
                    what='Exempt under Rule 3(c): commodity packaged for industrial or institutional consumers.',
                    why='Chapter II of the Legal Metrology (Packaged Commodities) Rules, 2011 exempts commodities meant for industrial or institutional consumers.',
                    source_image=source_file,
                    catalog_version=self.catalog_version,
                    catalog_hash=self.catalog_hash,
                )
                evaluations.append(ev)
                summary['not_applicable'] += 1
                continue

            if is_bulk_exempt:
                ev = RuleEvaluation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    legal_citation=rule.legal_citation,
                    status='NOT_APPLICABLE',
                    severity=rule.severity,
                    detected_value=str(gross_qty),
                    expected_condition=rule.expected_condition,
                    reason='Exempt under Rule 3(a): package net quantity exceeds 25 kg or 25 L.',
                    evidence_references=[source_file],
                    executable_status=rule.executable_status,
                    what='Exempt under Rule 3(a): package net quantity exceeds 25 kg or 25 L.',
                    why='Rule 3(a) exempts packages exceeding 25 kg or 25 L, unless specific commodity exceptions apply.',
                    source_image=source_file,
                    catalog_version=self.catalog_version,
                    catalog_hash=self.catalog_hash,
                )
                evaluations.append(ev)
                summary['not_applicable'] += 1
                continue

            # Dispatch rule evaluation
            if rule_id == 'PCR-001':
                ev = self._eval_pcr_001(rule, declarations, ocr_evidence, source_file)
            elif rule_id == 'PCR-002':
                ev = self._eval_pcr_002(rule, ctx, declarations, ocr_evidence, source_file)
            elif rule_id == 'PCR-003':
                ev = self._eval_pcr_003(rule, declarations, ocr_evidence, source_file)
            elif rule_id == 'PCR-004':
                ev = self._eval_pcr_004(rule, declarations, ocr_evidence, source_file)
            elif rule_id == 'PCR-005':
                ev = self._eval_pcr_005(rule, ctx, declarations, ocr_evidence, source_file)
            elif rule_id == 'PCR-006':
                ev = self._eval_pcr_006(rule, declarations, ocr_evidence, source_file)
            elif rule_id == 'PCR-007':
                ev = self._eval_pcr_007(
                    rule, ctx, declarations, ocr_evidence, source_file
                )
            elif rule_id == 'PCR-008':
                ev = self._eval_pcr_008(rule, declarations, ocr_evidence, source_file)
            else:
                # Fallback for unknown rule
                ev = RuleEvaluation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    legal_citation=rule.legal_citation,
                    status='MANUAL_REVIEW',
                    severity=rule.severity,
                    detected_value=None,
                    expected_condition=rule.expected_condition,
                    reason=f'No automated handler configured for rule {rule_id}.',
                    evidence_references=[source_file],
                    executable_status=rule.executable_status,
                    what=f'No automated handler configured for rule {rule_id}.',
                    why=rule.legal_citation,
                    source_image=source_file,
                    catalog_version=self.catalog_version,
                    catalog_hash=self.catalog_hash,
                )

            # Safety Guardrail Assertion: NEEDS_VERIFICATION rules must NEVER produce POTENTIAL_VIOLATION
            if rule.executable_status == 'NEEDS_VERIFICATION':
                if ev.status == 'POTENTIAL_VIOLATION':
                    ev.status = 'MANUAL_REVIEW'
                    ev.reason = (
                        f'[NEEDS_VERIFICATION Guardrail Enforced] {ev.reason}'
                    )

            # Update summary counts
            if ev.status == 'PASS':
                summary['passed'] += 1
            elif ev.status == 'POTENTIAL_VIOLATION':
                summary['potential_violations'] += 1
            elif ev.status == 'WARNING':
                summary['warnings'] += 1
            elif ev.status == 'MANUAL_REVIEW':
                summary['manual_review'] += 1
            elif ev.status == 'NOT_APPLICABLE':
                summary['not_applicable'] += 1

            ev.catalog_version = self.catalog_version
            ev.catalog_hash = self.catalog_hash
            evaluations.append(ev)

        report = ComplianceEvaluationReport(
            evaluation_id=str(uuid4()),
            inspection_id=context.inspection_id,
            catalog_version=self.catalog_version,
            catalog_hash=self.catalog_hash,
            inspection_date=effective_date_str,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            evaluations=evaluations,
        )
        return report

    # --- Individual Rule Evaluators ---

    def _eval_pcr_001(
        self,
        rule: RuleDefinition,
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        mfg_name = declarations.get('manufacturer_name')
        mfg_addr = declarations.get('manufacturer_address')

        has_name = not self._is_empty_or_none(mfg_name)
        has_addr = not self._is_empty_or_none(mfg_addr)

        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [mfg_name, mfg_addr, 'pvt', 'foods', 'limited', 'address'],
            source_file,
        )

        why = (
            f"Under {rule.legal_citation}, every pre-packaged commodity must declare "
            "the name and complete physical address of the manufacturer, packer, or importer."
        )

        if has_name and has_addr:
            detected = f'{mfg_name}; Address: {mfg_addr}'
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='PASS',
                severity=rule.severity,
                detected_value=detected,
                expected_condition=rule.expected_condition,
                reason='Manufacturer/packer identity and physical address are both declared.',
                evidence_references=[detected, source_file],
                executable_status=rule.executable_status,
                what=f'Compliant manufacturer and address declaration detected: {mfg_name}.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        missing_items = []
        if not has_name:
            missing_items.append('manufacturer/packer name')
        if not has_addr:
            missing_items.append('manufacturer/packer address')

        detected = (
            str(mfg_name)
            if has_name
            else (str(mfg_addr) if has_addr else None)
        )
        reason = f"Mandatory declaration missing under Rule 6(1)(a): {' and '.join(missing_items)} not detected."
        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='POTENTIAL_VIOLATION',
            severity=rule.severity,
            detected_value=detected,
            expected_condition=rule.expected_condition,
            reason=reason,
            evidence_references=[source_file],
            executable_status=rule.executable_status,
            what=reason,
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_002(
        self,
        rule: RuleDefinition,
        ctx: dict[str, Any],
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        coo = declarations.get('country_of_origin')
        has_coo = not self._is_empty_or_none(coo)

        is_imported = ctx.get('is_imported')

        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [coo, 'country of origin', 'made in', 'imported by'],
            source_file,
        )

        why = (
            f"Under {rule.legal_citation}, pre-packaged imported goods must declare "
            "the name of the country of origin or manufacture or assembly."
        )

        # If not explicitly indicated as imported, check if domestic or importer keywords exist
        if is_imported is False:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='NOT_APPLICABLE',
                severity=rule.severity,
                detected_value=str(coo) if has_coo else None,
                expected_condition=rule.expected_condition,
                reason='Rule 6(1)(aa) is not applicable to domestic products manufactured in India.',
                evidence_references=[source_file],
                executable_status=rule.executable_status,
                what='Domestic product: country of origin declaration under Rule 6(1)(aa) is not applicable.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        # If indicated as imported (or imported detected in context)
        if is_imported is True:
            if has_coo:
                return RuleEvaluation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    legal_citation=rule.legal_citation,
                    status='PASS',
                    severity=rule.severity,
                    detected_value=str(coo),
                    expected_condition=rule.expected_condition,
                    reason=f'Country of origin declared on imported package: {coo}.',
                    evidence_references=[str(coo), source_file],
                    executable_status=rule.executable_status,
                    what=f'Country of origin declared for imported product: {coo}.',
                    why=why,
                    evidence_snippet=snippet,
                    evidence_location=bbox,
                    ocr_confidence=conf,
                    source_image=src,
                )
            else:
                reason = 'Mandatory declaration missing under Rule 6(1)(aa): imported product lacks country of origin.'
                return RuleEvaluation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    legal_citation=rule.legal_citation,
                    status='POTENTIAL_VIOLATION',
                    severity=rule.severity,
                    detected_value=None,
                    expected_condition=rule.expected_condition,
                    reason=reason,
                    evidence_references=[source_file],
                    executable_status=rule.executable_status,
                    what=reason,
                    why=why,
                    evidence_snippet=snippet,
                    evidence_location=bbox,
                    ocr_confidence=conf,
                    source_image=src,
                )

        # If is_imported was not explicitly provided in inspection_context:
        # Check if country of origin is declared anyway
        if has_coo:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='PASS',
                severity=rule.severity,
                detected_value=str(coo),
                expected_condition=rule.expected_condition,
                reason=f'Country of origin declared: {coo}.',
                evidence_references=[str(coo), source_file],
                executable_status=rule.executable_status,
                what=f'Country of origin declared: {coo}.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        # Default for domestic retail if no import evidence:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='NOT_APPLICABLE',
            severity=rule.severity,
            detected_value=None,
            expected_condition=rule.expected_condition,
            reason='Package not designated as imported; Rule 6(1)(aa) is not applicable.',
            evidence_references=[source_file],
            executable_status=rule.executable_status,
            what='Package not designated as imported; Rule 6(1)(aa) is not applicable.',
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_003(
        self,
        rule: RuleDefinition,
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        comm_name = declarations.get('commodity_name')
        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [comm_name, 'rice', 'commodity'],
            source_file,
        )
        why = (
            f"Under {rule.legal_citation}, the common or generic name of the commodity "
            "must be clearly declared on the package."
        )

        if not self._is_empty_or_none(comm_name):
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='PASS',
                severity=rule.severity,
                detected_value=str(comm_name),
                expected_condition=rule.expected_condition,
                reason=f'Common or generic commodity name declared: {comm_name}.',
                evidence_references=[str(comm_name), source_file],
                executable_status=rule.executable_status,
                what=f'Common or generic commodity name declared: {comm_name}.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        reason = 'Mandatory declaration missing under Rule 6(1)(b): common or generic commodity name not declared.'
        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='POTENTIAL_VIOLATION',
            severity=rule.severity,
            detected_value=None,
            expected_condition=rule.expected_condition,
            reason=reason,
            evidence_references=[source_file],
            executable_status=rule.executable_status,
            what=reason,
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_004(
        self,
        rule: RuleDefinition,
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        net_qty = declarations.get('net_quantity')
        unit = declarations.get('quantity_unit')

        has_qty = not self._is_empty_or_none(net_qty)
        has_unit = not self._is_empty_or_none(unit)

        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [f'{net_qty} {unit}'.strip(), str(net_qty), str(unit)],
            source_file,
        )
        why = (
            f"Under {rule.legal_citation}, the net quantity must be declared using standard units "
            "of weight, measure, or number in approved metric symbols."
        )

        if not has_qty:
            reason = 'Mandatory declaration missing under Rule 6(1)(c): net quantity not declared.'
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='POTENTIAL_VIOLATION',
                severity=rule.severity,
                detected_value=None,
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        # Net quantity is present; validate numeric format and standard unit
        qty_str = str(net_qty).strip()
        unit_str = str(unit).strip().lower() if has_unit else ''

        # Extract number if attached
        num_match = re.search(r'^\d+(\.\d+)?', qty_str)
        is_numeric = num_match is not None

        if not is_numeric:
            reason = f"Net quantity value '{qty_str}' is not a valid positive numeric quantity."
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='POTENTIAL_VIOLATION',
                severity=rule.severity,
                detected_value=f'{qty_str} {unit_str}'.strip(),
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[qty_str, source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        if not has_unit or unit_str not in self.APPROVED_UNITS:
            reason = f"Non-standard or missing metric unit under Rule 6(1)(c): '{unit_str or 'None'}' is not an approved statutory unit."
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='POTENTIAL_VIOLATION',
                severity=rule.severity,
                detected_value=f'{qty_str} {unit_str}'.strip(),
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[f'{qty_str} {unit_str}'.strip(), source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        detected = f'{qty_str} {unit_str}'
        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='PASS',
            severity=rule.severity,
            detected_value=detected,
            expected_condition=rule.expected_condition,
            reason=f'Standard net quantity declaration verified: {detected}.',
            evidence_references=[detected, source_file],
            executable_status=rule.executable_status,
            what=f'Standard net quantity declaration verified: {detected}.',
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_005(
        self,
        rule: RuleDefinition,
        ctx: dict[str, Any],
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        category = str(ctx.get('commodity_category', '')).lower()
        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [declarations.get('month_year'), 'mfg', 'date', '202'],
            source_file,
        )
        why = (
            f"Under {rule.legal_citation}, the month and year in which the commodity is "
            "manufactured, packed, or pre-packed must be clearly declared on the package."
        )

        if category in {'bidi', 'incense_sticks', 'agarbatti', 'lpg'}:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='NOT_APPLICABLE',
                severity=rule.severity,
                detected_value=None,
                expected_condition=rule.expected_condition,
                reason='Exempt under Rule 6(1) Proviso (A) for bidi, agarbatti, or domestic LPG cylinder.',
                evidence_references=[source_file],
                executable_status=rule.executable_status,
                what='Exempt under Rule 6(1) Proviso (A) for bidi, agarbatti, or domestic LPG cylinder.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        m_y = declarations.get('month_year')
        if self._is_empty_or_none(m_y):
            reason = 'Mandatory declaration missing under Rule 6(1)(d): month and year of manufacture or packing not detected.'
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='POTENTIAL_VIOLATION',
                severity=rule.severity,
                detected_value=None,
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        m_y_str = str(m_y).strip()
        # Test for typical date patterns (MM/YYYY, MM-YYYY, MMM YYYY, etc.)
        valid_date_pat = re.search(
            r'(\b(0?[1-9]|1[0-2])[\/\-\.\s](20\d{2}|\d{2})\b)|(\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s\-\/\.]*(20\d{2}|\d{2})\b)',
            m_y_str,
            re.IGNORECASE,
        )
        if valid_date_pat:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='PASS',
                severity=rule.severity,
                detected_value=m_y_str,
                expected_condition=rule.expected_condition,
                reason=f'Valid month and year of manufacture declared: {m_y_str}.',
                evidence_references=[m_y_str, source_file],
                executable_status=rule.executable_status,
                what=f'Valid month and year of manufacture declared: {m_y_str}.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        # Declared but unparseable/ambiguous
        reason = f"Month and year declared in ambiguous or non-standard format: '{m_y_str}'."
        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='WARNING',
            severity='warning',
            detected_value=m_y_str,
            expected_condition=rule.expected_condition,
            reason=reason,
            evidence_references=[m_y_str, source_file],
            executable_status=rule.executable_status,
            what=reason,
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_006(
        self,
        rule: RuleDefinition,
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        # GUARDRAIL: NEVER PRODUCES POTENTIAL_VIOLATION
        bb_date = declarations.get('best_before_date')
        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [bb_date, 'best before', 'use by', 'expiry'],
            source_file,
        )
        why = (
            f"Under {rule.legal_citation}, best before or use-by date is required for "
            "perishable commodities, unless governed by another statute such as FSSA."
        )

        if not self._is_empty_or_none(bb_date):
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='PASS',
                severity=rule.severity,
                detected_value=str(bb_date),
                expected_condition=rule.expected_condition,
                reason=f'[Advisory / Non-executable] Best before or use-by declaration detected: {bb_date}.',
                evidence_references=[str(bb_date), source_file],
                executable_status=rule.executable_status,
                what=f'Best before or use-by date detected: {bb_date}.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='MANUAL_REVIEW',
            severity='warning',
            detected_value=None,
            expected_condition=rule.expected_condition,
            reason='[NEEDS_VERIFICATION] Commodity perishability and governing statute (e.g. FSSA) must be verified by officer. Automated violation is disabled.',
            evidence_references=[source_file],
            executable_status=rule.executable_status,
            what='Best before or use-by declaration requires manual verification for perishability and statutory exemptions.',
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_007(
        self,
        rule: RuleDefinition,
        ctx: dict[str, Any],
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        category = str(ctx.get('commodity_category', '')).lower()
        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            [declarations.get('retail_sale_price'), 'mrp', 'price', 'taxes', '299'],
            source_file,
        )
        why = (
            f"Under {rule.legal_citation}, the retail sale price must be declared in Indian currency "
            "clearly indicating that it is the Maximum Retail Price (MRP) inclusive of all taxes."
        )

        if category in {'bidi', 'lpg'}:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='NOT_APPLICABLE',
                severity=rule.severity,
                detected_value=None,
                expected_condition=rule.expected_condition,
                reason='Exempt under Rule 6(1) Proviso (C) for bidi or domestic LPG under Administrative Price Mechanism.',
                evidence_references=[source_file],
                executable_status=rule.executable_status,
                what='Exempt under Rule 6(1) Proviso (C) for bidi or domestic LPG under Administrative Price Mechanism.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        price = declarations.get('retail_sale_price')
        if self._is_empty_or_none(price):
            reason = 'Mandatory declaration missing under Rule 6(1)(e): retail sale price (MRP) not detected.'
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='POTENTIAL_VIOLATION',
                severity=rule.severity,
                detected_value=None,
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        price_str = str(price).strip()
        has_digits = bool(re.search(r'\d+', price_str))
        if not has_digits:
            reason = f"Retail sale price '{price_str}' contains no valid numeric amount."
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='POTENTIAL_VIOLATION',
                severity=rule.severity,
                detected_value=price_str,
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[price_str, source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        # Check for currency indicator and tax inclusiveness statement
        full_text = str(ocr_evidence.get('ocr_text', '')) + ' ' + price_str
        has_currency = bool(re.search(r'(₹|rs\.?|inr)', full_text, re.IGNORECASE))
        has_tax_statement = bool(
            re.search(
                r'(incl\w*\.?\s+of\s+all\s+taxes|inclusive\s+of\s+all\s+taxes|m\.?r\.?p\.?)',
                full_text,
                re.IGNORECASE,
            )
        )

        if has_currency and has_tax_statement:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='PASS',
                severity=rule.severity,
                detected_value=price_str,
                expected_condition=rule.expected_condition,
                reason=f'Maximum Retail Price (MRP) declared in Indian currency inclusive of all taxes: {price_str}.',
                evidence_references=[price_str, source_file],
                executable_status=rule.executable_status,
                what=f'Maximum Retail Price declared inclusive of all taxes: {price_str}.',
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        if not has_tax_statement:
            reason = f"Retail price declared ({price_str}) but explicit tax inclusiveness wording ('inclusive of all taxes') was not clearly detected."
            return RuleEvaluation(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                status='WARNING',
                severity='warning',
                detected_value=price_str,
                expected_condition=rule.expected_condition,
                reason=reason,
                evidence_references=[price_str, source_file],
                executable_status=rule.executable_status,
                what=reason,
                why=why,
                evidence_snippet=snippet,
                evidence_location=bbox,
                ocr_confidence=conf,
                source_image=src,
            )

        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='PASS',
            severity=rule.severity,
            detected_value=price_str,
            expected_condition=rule.expected_condition,
            reason=f'Retail sale price declared: {price_str}.',
            evidence_references=[price_str, source_file],
            executable_status=rule.executable_status,
            what=f'Retail sale price declared: {price_str}.',
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )

    def _eval_pcr_008(
        self,
        rule: RuleDefinition,
        declarations: dict[str, Any],
        ocr_evidence: dict[str, Any],
        source_file: str,
    ) -> RuleEvaluation:
        # GUARDRAIL: NEVER PRODUCES POTENTIAL_VIOLATION
        snippet, bbox, conf, src = self._extract_evidence(
            ocr_evidence,
            ['principal display panel', 'pdp'],
            source_file,
        )
        why = (
            f"Under {rule.legal_citation}, declarations must be grouped together on the principal display panel "
            "and font heights must comply with Table-I statutory minimums based on package area."
        )
        return RuleEvaluation(
            rule_id=rule.rule_id,
            title=rule.title,
            legal_citation=rule.legal_citation,
            status='MANUAL_REVIEW',
            severity='warning',
            detected_value=None,
            expected_condition=rule.expected_condition,
            reason='[NEEDS_VERIFICATION] Principal display panel font height (Table-I) and area calculations require physical scale calibration (mm) and container geometry. Automated violation is disabled.',
            evidence_references=[source_file],
            executable_status=rule.executable_status,
            what='Principal display panel layout and font height require physical dimensional verification by officer.',
            why=why,
            evidence_snippet=snippet,
            evidence_location=bbox,
            ocr_confidence=conf,
            source_image=src,
        )
