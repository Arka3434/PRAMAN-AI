from __future__ import annotations

from typing import Any


class DemoAnalysisService:
    @staticmethod
    def analyze_image(file_name: str, inspection_id: str) -> dict[str, Any]:
        return {
            'inspection_id': inspection_id,
            'status': 'completed',
            'confidence': 0.94,
            'structured_declarations': {
                'commodity_name': 'PRAMAN Premium Rice 5kg',
                'manufacturer_name': 'PRAMAN Foods Pvt Ltd',
                'manufacturer_address': '',
                'net_quantity': '',
                'quantity_unit': 'kg',
                'retail_sale_price': '₹299.00',
                'month_year': 'SEPT 2026',
                'consumer_contact': '+91 98765 43210',
                'country_of_origin': 'India',
                'source_file': file_name,
            },
        }
