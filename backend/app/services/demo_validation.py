from __future__ import annotations

from typing import Any


class DemoValidationService:
    @staticmethod
    def validate_declarations(structured_declarations: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        required_fields = {
            'commodity_name': 'Commodity name is missing from the declaration.',
            'manufacturer_name': 'Manufacturer name is missing from the declaration.',
            'manufacturer_address': 'Manufacturer address is missing from the declaration.',
            'net_quantity': 'Net quantity is missing from the declaration.',
            'quantity_unit': 'Quantity unit is missing from the declaration.',
            'retail_sale_price': 'Retail sale price is missing from the declaration.',
        }

        for field_name, description in required_fields.items():
            value = structured_declarations.get(field_name)
            if value in (None, '', ' '):
                findings.append(
                    {
                        'severity': 'warning',
                        'status': 'open',
                        'title': 'DEMO: required declaration missing',
                        'description': description,
                        'detected_value': str(value) if value is not None else None,
                        'rule_check_id': f'DEMO-REQ-{len(findings) + 1:03d}',
                        'evidence_reference': structured_declarations.get('source_file'),
                    }
                )

        if not findings:
            findings.append(
                {
                    'severity': 'pass',
                    'status': 'resolved',
                    'title': 'DEMO: required declaration check passed',
                    'description': 'All required demo declaration fields were present for this sample review.',
                    'detected_value': None,
                    'rule_check_id': 'DEMO-REQ-000',
                    'evidence_reference': structured_declarations.get('source_file'),
                }
            )

        return findings
