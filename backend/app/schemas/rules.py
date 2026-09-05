from __future__ import annotations

from pydantic import BaseModel, Field


class RuleDefinitionRead(BaseModel):
    rule_id: str
    title: str
    legal_citation: str
    source_document: str
    effective_from: str
    effective_to: str | None = None
    applicability: str
    exemptions: list[str] = Field(default_factory=list)
    input_fields: list[str] = Field(default_factory=list)
    check_type: str
    expected_condition: str
    severity: str
    executable_status: str
    evidence_requirement: str
    is_currently_effective: bool = True


class RuleCatalogRead(BaseModel):
    catalog_version: str
    catalog_hash: str
    jurisdiction: str
    regulatory_framework: str
    description: str
    last_updated: str
    coverage_notice: str
    total_rules: int
    safe_rules_count: int
    needs_verification_count: int
    rules: list[RuleDefinitionRead]
