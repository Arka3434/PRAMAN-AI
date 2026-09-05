from __future__ import annotations

import logging
import re
from typing import Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PanelDeclarationCandidate(BaseModel):
    image_id: str
    image_type: str  # front, back, left_side, right_side, other
    file_name: str
    storage_path: Optional[str] = None
    field_key: str
    raw_value: str
    normalized_value: str
    confidence: float = 0.0


class FusedFieldResult(BaseModel):
    field_key: str
    resolved_value: Optional[str] = None
    has_conflict: bool = False
    routing: str = "SAFE"  # "SAFE" | "MANUAL_REVIEW"
    conflict_description: Optional[str] = None
    candidates: List[PanelDeclarationCandidate] = Field(default_factory=list)
    primary_image_id: Optional[str] = None
    primary_image_type: Optional[str] = None
    primary_storage_path: Optional[str] = None


def normalize_field_value(field_key: str, value: Any) -> str:
    if value is None:
        return ""
    val_str = str(value).strip()
    if not val_str:
        return ""

    if field_key == "retail_sale_price":
        # Strip currency symbols, commas, decimals like .00
        cleaned = re.sub(r"[₹Rs\.inrINR,\s]", "", val_str)
        cleaned = re.sub(r"\.00$", "", cleaned)
        return cleaned

    if field_key == "net_quantity":
        # Lowercase, remove internal spaces between digits and units
        cleaned = val_str.lower().strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        # e.g. "5 kg" -> "5kg", "5.0 kg" -> "5kg"
        cleaned = re.sub(r"\.0(?=\s*[a-z])", "", cleaned)
        cleaned = re.sub(r"(\d+)\s+([a-z]+)", r"\1\2", cleaned)
        return cleaned

    # General normalization: collapse whitespace, lowercase
    return re.sub(r"\s+", " ", val_str.lower()).strip()


def values_are_materially_conflicting(field_key: str, norm_a: str, norm_b: str) -> bool:
    """
    Determines whether two non-empty normalized declaration values for the same field
    represent a genuine statutory contradiction rather than formatting/minor wording variation.
    """
    if not norm_a or not norm_b:
        return False
    if norm_a == norm_b:
        return False

    if field_key == "retail_sale_price":
        # Any difference in price value is a material conflict
        return norm_a != norm_b

    if field_key == "net_quantity":
        # Any difference in net quantity (e.g. 500g vs 1kg) is a material conflict
        return norm_a != norm_b

    if field_key == "month_year":
        # Differing packing dates are a material conflict
        return norm_a != norm_b

    if field_key == "country_of_origin":
        # Differing country names are a material conflict
        return norm_a != norm_b

    if field_key in ("commodity_name", "manufacturer_name", "manufacturer_address", "consumer_contact"):
        # If one is a complete substring of the other with high overlap, treat as non-conflicting elaboration
        if norm_a in norm_b or norm_b in norm_a:
            return False
        # Otherwise, distinct names/addresses are a material conflict
        return True

    return norm_a != norm_b


def fuse_panel_declarations(
    per_image_results: List[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, FusedFieldResult]]:
    """
    Fuses extracted structured declarations across multiple package panels into a unified
    package-level declaration set.

    STATUTORY INTEGRITY INVARIANTS:
    1. If materially different values for the same field are detected across panels,
       preserve both candidates and route that field to MANUAL_REVIEW.
    2. OCR confidence alone must NEVER establish legal truth when values conflict.
    3. Retain complete panel provenance (which image panel produced which value).
    """
    standard_fields = [
        "commodity_name",
        "manufacturer_name",
        "manufacturer_address",
        "net_quantity",
        "quantity_unit",
        "retail_sale_price",
        "month_year",
        "consumer_contact",
        "country_of_origin",
    ]

    field_candidates: dict[str, List[PanelDeclarationCandidate]] = {k: [] for k in standard_fields}

    for img_result in per_image_results:
        image_id = img_result.get("image_id", "")
        image_type = img_result.get("image_type", "other")
        file_name = img_result.get("file_name", "")
        storage_path = img_result.get("storage_path")
        declarations = img_result.get("structured_declarations", {})
        ocr_confidence = float(img_result.get("ocr_confidence", 0.0) or 0.0)

        for field_key in standard_fields:
            val = declarations.get(field_key)
            if val is not None and str(val).strip():
                raw_str = str(val).strip()
                norm_str = normalize_field_value(field_key, raw_str)
                field_candidates[field_key].append(
                    PanelDeclarationCandidate(
                        image_id=image_id,
                        image_type=image_type,
                        file_name=file_name,
                        storage_path=storage_path,
                        field_key=field_key,
                        raw_value=raw_str,
                        normalized_value=norm_str,
                        confidence=ocr_confidence,
                    )
                )

    fused_declarations: dict[str, Any] = {}
    fused_results: dict[str, FusedFieldResult] = {}

    for field_key in standard_fields:
        candidates = field_candidates[field_key]

        if not candidates:
            # Not detected on any panel
            fused_declarations[field_key] = None
            fused_results[field_key] = FusedFieldResult(
                field_key=field_key,
                resolved_value=None,
                has_conflict=False,
                routing="SAFE",
                candidates=[],
            )
            continue

        if len(candidates) == 1:
            # Detected on exactly one panel
            c = candidates[0]
            fused_declarations[field_key] = c.raw_value
            fused_results[field_key] = FusedFieldResult(
                field_key=field_key,
                resolved_value=c.raw_value,
                has_conflict=False,
                routing="SAFE",
                primary_image_id=c.image_id,
                primary_image_type=c.image_type,
                primary_storage_path=c.storage_path,
                candidates=candidates,
            )
            continue

        # Multiple candidates across panels: check for material conflict
        # Compare all pairs of candidates
        distinct_normalized = {}
        for c in candidates:
            if c.normalized_value not in distinct_normalized:
                distinct_normalized[c.normalized_value] = c

        has_conflict = False
        norm_keys = list(distinct_normalized.keys())
        for i in range(len(norm_keys)):
            for j in range(i + 1, len(norm_keys)):
                if values_are_materially_conflicting(field_key, norm_keys[i], norm_keys[j]):
                    has_conflict = True
                    break
            if has_conflict:
                break

        if has_conflict:
            # CRITICAL MANDATORY INVARIANT:
            # Do not pick a winner using OCR confidence.
            # Preserve all candidates and route to MANUAL_REVIEW.
            conflict_descriptions = [
                f"{c.image_type.upper()} ({c.file_name}): '{c.raw_value}'"
                for c in candidates
            ]
            conflict_msg = (
                f"Conflicting declarations detected across panels: "
                f"{'; '.join(conflict_descriptions)}. Manual inspector review is legally mandatory."
            )

            # For the raw declaration value, provide the primary candidate but flag the conflict
            fused_declarations[field_key] = candidates[0].raw_value
            fused_results[field_key] = FusedFieldResult(
                field_key=field_key,
                resolved_value=candidates[0].raw_value,
                has_conflict=True,
                routing="MANUAL_REVIEW",
                conflict_description=conflict_msg,
                primary_image_id=candidates[0].image_id,
                primary_image_type=candidates[0].image_type,
                primary_storage_path=candidates[0].storage_path,
                candidates=candidates,
            )
            logger.info("Panel fusion flagged conflict on %s: %s", field_key, conflict_msg)

        else:
            # Non-conflicting: duplicate or equivalent detections across panels
            # Sort by candidate raw value length (more descriptive) or confidence for deduplication
            best_candidate = max(candidates, key=lambda c: (len(c.raw_value), c.confidence))
            fused_declarations[field_key] = best_candidate.raw_value
            fused_results[field_key] = FusedFieldResult(
                field_key=field_key,
                resolved_value=best_candidate.raw_value,
                has_conflict=False,
                routing="SAFE",
                primary_image_id=best_candidate.image_id,
                primary_image_type=best_candidate.image_type,
                primary_storage_path=best_candidate.storage_path,
                candidates=candidates,
            )

    return fused_declarations, fused_results
