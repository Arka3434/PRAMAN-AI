from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.rules import RuleCatalogRead, RuleDefinitionRead
from app.services.compliance_engine import ComplianceEngine, parse_iso_date

router = APIRouter(prefix="/api/v1/rules", tags=["legal-rules"])

# Global shared instance of the deterministic compliance engine
_engine = ComplianceEngine()


def _get_catalog_raw_metadata() -> dict[str, str]:
    """Read the catalog top-level descriptive metadata from the validated source."""
    path = _engine.catalog_path
    data = json.loads(path.read_bytes().decode("utf-8"))
    return {
        "jurisdiction": data.get("jurisdiction", "India"),
        "regulatory_framework": data.get(
            "regulatory_framework",
            "Legal Metrology (Packaged Commodities) Rules, 2011 (as amended)",
        ),
        "description": data.get(
            "description",
            "Versioned statutory rule catalog under Chapter II of PCR 2011.",
        ),
        "last_updated": data.get("last_updated", "2026-09-02"),
    }


@router.get("", response_model=RuleCatalogRead)
def get_rule_catalog(
    rule_status: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by executable status: SAFE or NEEDS_VERIFICATION",
        ),
    ] = None,
    search: Annotated[
        str | None,
        Query(
            description="Search term matching Rule ID, title, or legal citation"
        ),
    ] = None,
    effective_on: Annotated[
        str | None,
        Query(
            description="Evaluate rule effectiveness as of this date (ISO format YYYY-MM-DD)"
        ),
    ] = None,
    current_user: User = Depends(require_permission(Permission.RULES_READ)),
) -> RuleCatalogRead:

    """Retrieve the versioned statutory legal rule catalog with cryptographic integrity hash.

    Strictly read-only statutory reference endpoint.
    """
    metadata = _get_catalog_raw_metadata()

    # Determine evaluation date for effectiveness check
    eval_date = date.today()
    if effective_on:
        try:
            eval_date = parse_iso_date(effective_on)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid effective_on date parameter: {exc}",
            ) from exc

    rule_items: list[RuleDefinitionRead] = []
    for rule in _engine.rules.values():
        is_eff = rule.is_effective(eval_date)

        # Filter by status if requested (case-insensitive)
        if rule_status:
            if rule.executable_status.upper() != rule_status.strip().upper():
                continue

        # Filter by search term if requested
        if search:
            q = search.strip().lower()
            matches = (
                q in rule.rule_id.lower()
                or q in rule.title.lower()
                or q in rule.legal_citation.lower()
                or q in rule.applicability.lower()
            )
            if not matches:
                continue

        rule_items.append(
            RuleDefinitionRead(
                rule_id=rule.rule_id,
                title=rule.title,
                legal_citation=rule.legal_citation,
                source_document=rule.source_document,
                effective_from=rule.effective_from,
                effective_to=rule.effective_to,
                applicability=rule.applicability,
                exemptions=rule.exemptions,
                input_fields=rule.input_fields,
                check_type=rule.check_type,
                expected_condition=rule.expected_condition,
                severity=rule.severity,
                executable_status=rule.executable_status,
                evidence_requirement=rule.evidence_requirement,
                is_currently_effective=is_eff,
            )
        )

    all_rules = list(_engine.rules.values())
    safe_count = sum(1 for r in all_rules if r.executable_status == "SAFE")
    needs_verif_count = sum(
        1 for r in all_rules if r.executable_status == "NEEDS_VERIFICATION"
    )

    coverage_notice = (
        "Statutory pre-packaged commodities declarations codified under Chapter II "
        "of the Legal Metrology (Packaged Commodities) Rules, 2011. This catalog serves as "
        "an algorithmic auditing and decision-support tool. It does not replace the statutory "
        "inspection powers or judicial discretion vested in Legal Metrology Officers under "
        "the Legal Metrology Act, 2009."
    )

    return RuleCatalogRead(
        catalog_version=_engine.catalog_version,
        catalog_hash=_engine.catalog_hash,
        jurisdiction=metadata["jurisdiction"],
        regulatory_framework=metadata["regulatory_framework"],
        description=metadata["description"],
        last_updated=metadata["last_updated"],
        coverage_notice=coverage_notice,
        total_rules=len(all_rules),
        safe_rules_count=safe_count,
        needs_verification_count=needs_verif_count,
        rules=rule_items,
    )


@router.get("/{rule_id}", response_model=RuleDefinitionRead)
def get_rule_detail(
    rule_id: str,
    effective_on: Annotated[
        str | None,
        Query(
            description="Evaluate rule effectiveness as of this date (ISO format YYYY-MM-DD)"
        ),
    ] = None,
    current_user: User = Depends(require_permission(Permission.RULES_READ)),
) -> RuleDefinitionRead:

    """Retrieve detailed statutory information for a single codified rule."""
    normalized_id = rule_id.strip().upper()
    rule = _engine.rules.get(normalized_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID '{rule_id}' not found in catalog v{_engine.catalog_version}.",
        )

    eval_date = date.today()
    if effective_on:
        try:
            eval_date = parse_iso_date(effective_on)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid effective_on date parameter: {exc}",
            ) from exc

    return RuleDefinitionRead(
        rule_id=rule.rule_id,
        title=rule.title,
        legal_citation=rule.legal_citation,
        source_document=rule.source_document,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        applicability=rule.applicability,
        exemptions=rule.exemptions,
        input_fields=rule.input_fields,
        check_type=rule.check_type,
        expected_condition=rule.expected_condition,
        severity=rule.severity,
        executable_status=rule.executable_status,
        evidence_requirement=rule.evidence_requirement,
        is_currently_effective=rule.is_effective(eval_date),
    )
