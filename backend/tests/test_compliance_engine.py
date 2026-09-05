from __future__ import annotations

import json
from app.services.compliance_engine import (
    ComplianceEngine,
    InspectionEvaluationContext,
)


def get_sample_compliant_context() -> InspectionEvaluationContext:
    return InspectionEvaluationContext(
        inspection_id='test-insp-001',
        inspection_context={
            'is_imported': False,
            'commodity_category': 'packaged_food',
            'consumer_type': 'retail',
        },
        structured_declarations={
            'commodity_name': 'PRAMAN Premium Basmati Rice',
            'manufacturer_name': 'PRAMAN Foods Pvt Ltd',
            'manufacturer_address': 'Plot 12, Industrial Area, Hyderabad, Telangana 500001',
            'net_quantity': '5',
            'quantity_unit': 'kg',
            'month_year': 'SEPT 2026',
            'retail_sale_price': '₹299.00',
            'country_of_origin': None,
            'source_file': 'rice_front.jpg',
        },
        ocr_evidence={
            'ocr_text': (
                'PRAMAN Premium Basmati Rice\n'
                'PRAMAN Foods Pvt Ltd\n'
                'Plot 12, Industrial Area, Hyderabad, Telangana 500001\n'
                'Net Quantity: 5 kg\n'
                'Mfg Date: SEPT 2026\n'
                'MRP Rs 299.00 (inclusive of all taxes)\n'
            ),
            'ocr_confidence': 0.94,
            'source_file': 'rice_front.jpg',
        },
    )


def test_catalog_loading_and_integrity() -> None:
    engine = ComplianceEngine()
    assert engine.catalog_version == '1.0.0'
    assert len(engine.catalog_hash) == 64
    assert len(engine.rules) == 8
    assert 'PCR-001' in engine.rules
    assert 'PCR-008' in engine.rules
    assert engine.rules['PCR-006'].executable_status == 'NEEDS_VERIFICATION'
    assert engine.rules['PCR-008'].executable_status == 'NEEDS_VERIFICATION'
    assert engine.rules['PCR-001'].executable_status == 'SAFE'


def test_fully_compliant_declarations() -> None:
    """1. Test fully compliant declarations produce PASS for applicable SAFE rules."""
    engine = ComplianceEngine()
    ctx = get_sample_compliant_context()
    report = engine.evaluate(ctx)

    assert report.inspection_id == 'test-insp-001'
    assert report.catalog_version == '1.0.0'
    assert report.summary['potential_violations'] == 0

    eval_by_id = {ev.rule_id: ev for ev in report.evaluations}

    # PCR-001: Name & address
    assert eval_by_id['PCR-001'].status == 'PASS'
    # PCR-002: Domestic product, should be NOT_APPLICABLE
    assert eval_by_id['PCR-002'].status == 'NOT_APPLICABLE'
    # PCR-003: Commodity name
    assert eval_by_id['PCR-003'].status == 'PASS'
    # PCR-004: Net quantity
    assert eval_by_id['PCR-004'].status == 'PASS'
    # PCR-005: Month & year
    assert eval_by_id['PCR-005'].status == 'PASS'
    # PCR-007: Retail sale price
    assert eval_by_id['PCR-007'].status == 'PASS'

    # Verify findings projection compatibility
    findings = report.to_findings_projection()
    assert isinstance(findings, list)
    assert len(findings) > 0
    for f in findings:
        assert 'inspection_id' in f
        assert 'severity' in f
        assert 'status' in f
        assert 'title' in f
        assert 'description' in f
        assert 'rule_check_id' in f


def test_missing_mandatory_declaration() -> None:
    """2. Test missing mandatory manufacturer details produces POTENTIAL_VIOLATION."""
    engine = ComplianceEngine()
    ctx = get_sample_compliant_context()
    ctx.structured_declarations['manufacturer_name'] = None
    ctx.structured_declarations['manufacturer_address'] = None

    report = engine.evaluate(ctx)
    eval_by_id = {ev.rule_id: ev for ev in report.evaluations}

    pcr_001 = eval_by_id['PCR-001']
    assert pcr_001.status == 'POTENTIAL_VIOLATION'
    assert pcr_001.severity == 'critical'
    assert 'missing' in pcr_001.reason.lower()
    assert report.summary['potential_violations'] >= 1


def test_imported_product_without_country_of_origin() -> None:
    """3. Test imported product without country of origin produces POTENTIAL_VIOLATION."""
    engine = ComplianceEngine()
    ctx = get_sample_compliant_context()
    ctx.inspection_context['is_imported'] = True
    ctx.structured_declarations['country_of_origin'] = None

    report = engine.evaluate(ctx)
    eval_by_id = {ev.rule_id: ev for ev in report.evaluations}

    pcr_002 = eval_by_id['PCR-002']
    assert pcr_002.status == 'POTENTIAL_VIOLATION'
    assert pcr_002.severity == 'critical'
    assert 'country of origin' in pcr_002.reason.lower()

    # Now provide country of origin, it should PASS
    ctx.structured_declarations['country_of_origin'] = 'Thailand'
    report_pass = engine.evaluate(ctx)
    eval_by_id_pass = {ev.rule_id: ev for ev in report_pass.evaluations}
    assert eval_by_id_pass['PCR-002'].status == 'PASS'


def test_invalid_quantity_unit() -> None:
    """4. Test non-standard metric quantity unit produces POTENTIAL_VIOLATION."""
    engine = ComplianceEngine()
    ctx = get_sample_compliant_context()
    ctx.structured_declarations['net_quantity'] = '10'
    ctx.structured_declarations['quantity_unit'] = 'lbs'  # non-statutory unit in India

    report = engine.evaluate(ctx)
    eval_by_id = {ev.rule_id: ev for ev in report.evaluations}

    pcr_004 = eval_by_id['PCR-004']
    assert pcr_004.status == 'POTENTIAL_VIOLATION'
    assert pcr_004.severity == 'critical'
    assert 'non-standard' in pcr_004.reason.lower()


def test_needs_verification_rules_cannot_create_violations() -> None:
    """5. Test NEEDS_VERIFICATION rules (PCR-006 and PCR-008) NEVER produce POTENTIAL_VIOLATION."""
    engine = ComplianceEngine()
    # Completely empty context
    ctx = InspectionEvaluationContext(
        inspection_id='test-empty-002',
        inspection_context={'consumer_type': 'retail'},
        structured_declarations={},
        ocr_evidence={},
    )
    report = engine.evaluate(ctx)
    eval_by_id = {ev.rule_id: ev for ev in report.evaluations}

    # Even with missing best_before_date and no PDP calibration:
    assert eval_by_id['PCR-006'].status != 'POTENTIAL_VIOLATION'
    assert eval_by_id['PCR-006'].status == 'MANUAL_REVIEW'

    assert eval_by_id['PCR-008'].status != 'POTENTIAL_VIOLATION'
    assert eval_by_id['PCR-008'].status == 'MANUAL_REVIEW'


def test_deterministic_repeated_evaluation() -> None:
    """6. Test repeated evaluation over same input produces identical output."""
    engine = ComplianceEngine()
    ctx = get_sample_compliant_context()

    first_run = engine.evaluate(ctx)
    first_dump = json.dumps(
        {
            'summary': first_run.summary,
            'evaluations': [e.to_dict() for e in first_run.evaluations],
            'findings': first_run.to_findings_projection(),
        },
        sort_keys=True,
    )

    for _ in range(5):
        subsequent_run = engine.evaluate(ctx)
        subsequent_dump = json.dumps(
            {
                'summary': subsequent_run.summary,
                'evaluations': [e.to_dict() for e in subsequent_run.evaluations],
                'findings': subsequent_run.to_findings_projection(),
            },
            sort_keys=True,
        )
        assert first_dump == subsequent_dump, 'Evaluation output must be strictly deterministic across iterations'
