from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class QualityVerdict(str, Enum):
    ACCEPTABLE = "ACCEPTABLE"
    WARNING_DEGRADED = "WARNING_DEGRADED"
    UNREADABLE = "UNREADABLE"


class ImageQualityReport(BaseModel):
    """
    Evidence-quality diagnostic assessment for an uploaded inspection image.
    NOTE: Image quality is an engineering diagnostic heuristic, NOT a statutory
    or legal compliance evaluation. It does not create legal findings.
    """
    sharpness_score: float = Field(
        ...,
        description="Raw variance of the Laplacian operator on grayscale image. Higher indicates sharper focus."
    )
    glare_percentage: float = Field(
        ...,
        description="Percentage of pixels clipped at or near maximum luminance (>250/255)."
    )
    width: int = Field(
        ...,
        description="Image width in pixels."
    )
    height: int = Field(
        ...,
        description="Image height in pixels."
    )
    resolution_adequate: bool = Field(
        ...,
        description="Engineering heuristic indicating whether image dimensions are sufficient for reliable OCR (>400x400)."
    )
    quality_verdict: QualityVerdict = Field(
        ...,
        description="Deterministic assessment: ACCEPTABLE, WARNING_DEGRADED, or UNREADABLE."
    )
    issues: List[str] = Field(
        default_factory=list,
        description="List of detected photographic degradation issues."
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Inspector guidance/recommendations (e.g. retake with better lighting or focus)."
    )
