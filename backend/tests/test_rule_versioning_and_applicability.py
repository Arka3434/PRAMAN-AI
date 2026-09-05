"""Phase 6E Tests: Versioned Legal Rule Catalog & Applicability.

Tests temporal effectiveness, future-effective rule guardrails, open-ended
effective_to handling, applicability/exemptions, catalog version/hash traceability,
and safety classification preservation.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.compliance_engine import (
    ComplianceEngine,
    InspectionEvaluationContext,
    RuleDefinition,
    parse_iso_date,
)


@pytest.fixture
def engine() -> ComplianceEngine:
    return ComplianceEngine()


def test_rule_active_on_effective_from_date(engine: ComplianceEngine) -> None:
    """1. Rule must be active on its exact effective_from date."""
    # PCR-001 came into force on 2011-04-01
    assert engine.is_rule_effective('PCR-001', '2011-04-01') is True
    assert engine.is_rule_effective('PCR-001', date(2011, 4, 1)) is True

    # PCR-002 came into force on 2018-01-01
    assert engine.is_rule_effective('PCR-002', '2018-01-01') is True
    assert engine.is_rule_effective('PCR-002', date(2018, 1, 1)) is True

    # Evaluated report on effective_from date considers rule active
    ctx = InspectionEvaluationContext(
        inspection_id='test-insp-from-date',
        inspection_date='2018-01-01',
        inspection_context={'is_imported': True},
        structured_declarations={'country_of_origin': 'Germany'},
    )
    report = engine.evaluate(ctx)
    pcr_002_ev = next(e for e in report.evaluations if e.rule_id == 'PCR-002')
    assert pcr_002_ev.status == 'PASS'


def test_rule_inactive_before_effective_from(engine: ComplianceEngine) -> None:
    """2. Rule must be inactive before its effective_from date."""
    # PCR-001 inactive before 2011-04-01
    assert engine.is_rule_effective('PCR-001', '2011-03-31') is False
    assert engine.is_rule_effective('PCR-001', '2010-01-01') is False

    # PCR-002 inactive before 2018-01-01
    assert engine.is_rule_effective('PCR-002', '2017-12-31') is False
    assert engine.is_rule_effective('PCR-002', '2015-06-15') is False

    # Evaluation on 2015-06-15 sets PCR-002 to NOT_APPLICABLE
    ctx = InspectionEvaluationContext(
        inspection_id='test-insp-before-date',
        inspection_date='2015-06-15',
        inspection_context={'is_imported': True},
        structured_declarations={},  # Missing COO would fail in 2018+
    )
    report = engine.evaluate(ctx)
    pcr_002_ev = next(e for e in report.evaluations if e.rule_id == 'PCR-002')
    assert pcr_002_ev.status == 'NOT_APPLICABLE'
    assert 'effective from 2018-01-01' in pcr_002_ev.reason


def test_rule_inactive_after_effective_to() -> None:
    """3. Rule must be inactive after its effective_to date."""
    temp_rule = RuleDefinition(
        rule_id='TEST-001',
        title='Temporary Specification Rule',
        legal_citation='PCR 2011 Temporary Notification',
        source_document='TEST.pdf',
        effective_from='2020-01-01',
        effective_to='2022-12-31',
        applicability='Temporary test commodity',
        exemptions=[],
        input_fields=['test_field'],
        check_type='presence',
        expected_condition='Test condition',
        severity='major',
        executable_status='SAFE',
        evidence_requirement='Test requirement',
    )

    assert temp_rule.is_effective('2020-01-01') is True
    assert temp_rule.is_effective('2021-06-15') is True
    assert temp_rule.is_effective('2022-12-31') is True
    assert temp_rule.is_effective('2023-01-01') is False
    assert temp_rule.is_effective('2026-09-03') is False


def test_open_ended_effective_to(engine: ComplianceEngine) -> None:
    """4. Open-ended effective_to (null) means rule remains active indefinitely."""
    for rule in engine.rules.values():
        assert rule.effective_to is None
        # Must be active on current date
        assert rule.is_effective('2026-09-03') is True
        # Must remain active on future dates
        assert rule.is_effective('2035-12-31') is True


def test_future_effective_rule_not_applied_to_earlier_inspection(engine: ComplianceEngine) -> None:
    """5. Rules with future effective_from must NOT create violations for earlier inspections."""
    # PCR-002 (effective 2018-01-01): imported product without country of origin
    # Evaluated for an inspection conducted on 2016-10-10
    ctx_2016 = InspectionEvaluationContext(
        inspection_id='insp-2016',
        inspection_date='2016-10-10',
        inspection_context={'is_imported': True},
        structured_declarations={
            'manufacturer_name': 'Global Importers Ltd',
            'manufacturer_address': 'Mumbai, India',
            'commodity_name': 'Olive Oil',
            'net_quantity': 500,
            'quantity_unit': 'ml',
            'month_year': '05/2016',
            'retail_sale_price': 'Rs. 450.00',
            # country_of_origin is intentionally MISSING
        },
    )
    report_2016 = engine.evaluate(ctx_2016)
    eval_pcr_002_2016 = next(e for e in report_2016.evaluations if e.rule_id == 'PCR-002')
    # Must NOT produce POTENTIAL_VIOLATION for 2016 inspection
    assert eval_pcr_002_2016.status == 'NOT_APPLICABLE'

    # Now evaluate identical package evidence for an inspection on 2020-01-01
    ctx_2020 = InspectionEvaluationContext(
        inspection_id='insp-2020',
        inspection_date='2020-01-01',
        inspection_context={'is_imported': True},
        structured_declarations=ctx_2016.structured_declarations,
    )
    report_2020 = engine.evaluate(ctx_2020)
    eval_pcr_002_2020 = next(e for e in report_2020.evaluations if e.rule_id == 'PCR-002')
    # For 2020, missing country of origin IS a potential violation
    assert eval_pcr_002_2020.status == 'POTENTIAL_VIOLATION'


def test_applicability_and_exemption_handling(engine: ComplianceEngine) -> None:
    """6. Evaluation layer accurately distinguishes applicable vs not-applicable."""
    # A. Industrial consumer exemption (Rule 3(c))
    ctx_ind = InspectionEvaluationContext(
        inspection_id='insp-industrial',
        inspection_context={'consumer_type': 'industrial'},
        structured_declarations={},
    )
    rep_ind = engine.evaluate(ctx_ind)
    assert rep_ind.summary['not_applicable'] == len(engine.rules)
    assert all(e.status == 'NOT_APPLICABLE' for e in rep_ind.evaluations)
    assert len(rep_ind.to_findings_projection()) == 0

    # B. Bulk quantity exemption (Rule 3(a))
    ctx_bulk = InspectionEvaluationContext(
        inspection_id='insp-bulk',
        inspection_context={
            'consumer_type': 'retail',
            'package_gross_quantity': 35.0,
            'package_quantity_unit': 'kg',
            'commodity_category': 'detergent',
        },
        structured_declarations={},
    )
    rep_bulk = engine.evaluate(ctx_bulk)
    assert rep_bulk.summary['not_applicable'] == len(engine.rules)
    assert all(e.status == 'NOT_APPLICABLE' for e in rep_bulk.evaluations)

    # C. Domestic commodity: PCR-002 not applicable, others applicable
    ctx_dom = InspectionEvaluationContext(
        inspection_id='insp-domestic',
        inspection_context={'is_imported': False},
        structured_declarations={
            'manufacturer_name': 'Acme Ltd',
            'manufacturer_address': 'New Delhi',
            'commodity_name': 'Tea',
            'net_quantity': 250,
            'quantity_unit': 'g',
            'month_year': '01/2026',
            'retail_sale_price': 'Rs. 100.00',
        },
    )
    rep_dom = engine.evaluate(ctx_dom)
    pcr_002 = next(e for e in rep_dom.evaluations if e.rule_id == 'PCR-002')
    assert pcr_002.status == 'NOT_APPLICABLE'
    pcr_001 = next(e for e in rep_dom.evaluations if e.rule_id == 'PCR-001')
    assert pcr_001.status == 'PASS'

    # D. Bidi / LPG commodity category exemption under Rule 6(1) Proviso (A) and (C)
    ctx_bidi = InspectionEvaluationContext(
        inspection_id='insp-bidi',
        inspection_context={'commodity_category': 'bidi', 'is_imported': False},
        structured_declarations={
            'manufacturer_name': 'Bidi Works',
            'manufacturer_address': 'Jabalpur, MP',
            'commodity_name': 'Bidi',
            'net_quantity': 25,
            'quantity_unit': 'pieces',
        },
    )
    rep_bidi = engine.evaluate(ctx_bidi)
    pcr_005 = next(e for e in rep_bidi.evaluations if e.rule_id == 'PCR-005')
    pcr_007 = next(e for e in rep_bidi.evaluations if e.rule_id == 'PCR-007')
    assert pcr_005.status == 'NOT_APPLICABLE'
    assert pcr_007.status == 'NOT_APPLICABLE'


def test_catalog_version_and_hash_traceability(engine: ComplianceEngine) -> None:
    """7. Catalog version and hash remain attached to evaluations and report."""
    expected_hash = (
        'b847e70c09bf2666cee117f0b800b8f26de5d5d86059d70966d794a5e6e13adc'
    )
    assert engine.catalog_version == '1.0.0'
    assert engine.catalog_hash == expected_hash

    ctx = InspectionEvaluationContext(
        inspection_id='insp-traceability',
        inspection_date='2026-09-03',
        structured_declarations={
            'manufacturer_name': 'Hindustan Consumer Products',
            'manufacturer_address': 'Plot 10, Okhla Phase III, New Delhi',
            'commodity_name': 'Atta',
            'net_quantity': 5,
            'quantity_unit': 'kg',
            'month_year': '08/2026',
            'retail_sale_price': 'Rs. 240.00 (incl. of all taxes)',
        },
    )
    report = engine.evaluate(ctx)

    # Attached to report
    assert report.catalog_version == '1.0.0'
    assert report.catalog_hash == expected_hash
    assert report.inspection_date == '2026-09-03'

    # Attached to every individual evaluation
    for ev in report.evaluations:
        assert ev.catalog_version == '1.0.0'
        assert ev.catalog_hash == expected_hash

    # Attached to findings projection
    findings = report.to_findings_projection()
    assert len(findings) > 0
    for finding in findings:
        assert finding['catalog_version'] == '1.0.0'
        assert finding['catalog_hash'] == expected_hash
        ev_data = json.loads(finding['evidence_reference'])
        assert ev_data['catalog_version'] == '1.0.0'
        assert ev_data['catalog_hash'] == expected_hash
        assert ev_data['inspection_date'] == '2026-09-03'


def test_needs_verification_rules_remain_manual_review_only(engine: ComplianceEngine) -> None:
    """9. NEEDS_VERIFICATION rules (PCR-006, PCR-008) must never produce POTENTIAL_VIOLATION."""
    ctx = InspectionEvaluationContext(
        inspection_id='insp-safety-guardrails',
        structured_declarations={},  # All declarations missing
    )
    report = engine.evaluate(ctx)

    pcr_006 = next(e for e in report.evaluations if e.rule_id == 'PCR-006')
    pcr_008 = next(e for e in report.evaluations if e.rule_id == 'PCR-008')

    assert pcr_006.executable_status == 'NEEDS_VERIFICATION'
    assert pcr_006.status == 'MANUAL_REVIEW'
    assert pcr_006.status != 'POTENTIAL_VIOLATION'

    assert pcr_008.executable_status == 'NEEDS_VERIFICATION'
    assert pcr_008.status == 'MANUAL_REVIEW'
    assert pcr_008.status != 'POTENTIAL_VIOLATION'


def test_date_parser_utility() -> None:
    """Helper date parsing handles multiple representations reliably."""
    assert parse_iso_date('2026-09-03') == date(2026, 9, 3)
    assert parse_iso_date('2026/09/03') == date(2026, 9, 3)
    assert parse_iso_date('2026-09-03T14:30:00Z') == date(2026, 9, 3)
    assert parse_iso_date(date(2026, 9, 3)) == date(2026, 9, 3)

    with pytest.raises(ValueError):
        parse_iso_date('not-a-date')

    with pytest.raises(TypeError):
        parse_iso_date(12345)
