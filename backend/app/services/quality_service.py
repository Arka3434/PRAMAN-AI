import json
import logging
from pathlib import Path
from typing import Union, Tuple, List, Optional
import cv2
import numpy as np

from app.schemas.quality import QualityVerdict, ImageQualityReport

logger = logging.getLogger(__name__)

# ==============================================================================
# Deterministic Image Quality Engineering Thresholds
# NOTE: These are empirical engineering heuristics for packaging text legibility
# and OCR reliability. They are NOT statutory legal compliance requirements.
# ==============================================================================
SHARPNESS_ACCEPTABLE_MIN = 100.0   # Laplacian variance >= 100 is considered sharp
SHARPNESS_DEGRADED_MIN = 50.0      # 50 <= Var < 100 is moderately blurred; < 50 is unreadable

GLARE_ACCEPTABLE_MAX = 5.0         # <= 5.0% clipped luminance pixels is acceptable
GLARE_DEGRADED_MAX = 15.0          # 5.0% < Glare <= 15.0% is degraded; > 15.0% is unreadable

RESOLUTION_MIN_DIMENSION = 400     # Minimum width and height in px for acceptable resolution
RESOLUTION_CRITICAL_DIMENSION = 200 # Dimensions below this make fine print virtually unrecoverable
RESOLUTION_MIN_PIXELS = 200_000    # e.g., 500x400 ~ 200k pixels


def calculate_sharpness(gray_img: np.ndarray) -> float:
    """
    Computes raw Laplacian variance of a grayscale image.
    Higher variance corresponds to sharper edge transitions.
    """
    laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
    variance = float(laplacian.var())
    return round(variance, 2)


def calculate_glare_percentage(gray_img: np.ndarray) -> float:
    """
    Calculates the percentage of pixels clipped at or near peak luminance (>250).
    Represents flash reflection or bright direct lighting obscuring packaging foil/labels.

    ENGINEERING RATIONALE & CALIBRATION:
    Packaged goods frequently feature white paper or white plastic label panels with
    high-contrast dark text. If the image has a predominantly white substrate
    (median >= 230) and contains high-contrast dark text (min < 100, std > 25),
    the white pixels represent the packaging substrate itself rather than specular glare.
    Otherwise, high-luminance clipped pixels represent flash or directional light reflections.
    """
    total_pixels = gray_img.size
    if total_pixels == 0:
        return 0.0

    clipped_pixels = int(np.count_nonzero(gray_img > 250))
    if clipped_pixels == 0:
        return 0.0

    # Check if this is a high-contrast white label substrate rather than specular glare
    median_val = float(np.median(gray_img))
    min_val = float(np.min(gray_img))
    std_val = float(np.std(gray_img))

    if median_val >= 230 and min_val < 100 and std_val > 25:
        # High contrast white label: background is legitimate packaging substrate
        return 0.0

    percentage = (clipped_pixels / total_pixels) * 100.0
    return round(percentage, 2)


def assess_image_quality(
    image_input: Union[str, Path, np.ndarray]
) -> ImageQualityReport:
    """
    Deterministic Computer Vision Quality Diagnostic.
    Evaluates:
      1. Sharpness (Laplacian variance)
      2. Glare percentage (high-luminance clipping)
      3. Resolution adequacy (dimensions vs heuristic minimums)
      4. Overall categorical verdict (ACCEPTABLE, WARNING_DEGRADED, UNREADABLE)
    """
    img: Optional[np.ndarray] = None
    if isinstance(image_input, (str, Path)):
        file_path = Path(image_input)
        if not file_path.exists():
            return ImageQualityReport(
                sharpness_score=0.0,
                glare_percentage=0.0,
                width=0,
                height=0,
                resolution_adequate=False,
                quality_verdict=QualityVerdict.UNREADABLE,
                issues=["Image file not found on disk."],
                recommendations=["Re-upload or recapture the packaging image."]
            )
        img = cv2.imread(str(file_path))
    elif isinstance(image_input, np.ndarray):
        img = image_input

    if img is None or img.size == 0:
        return ImageQualityReport(
            sharpness_score=0.0,
            glare_percentage=0.0,
            width=0,
            height=0,
            resolution_adequate=False,
            quality_verdict=QualityVerdict.UNREADABLE,
            issues=["Unable to decode image data."],
            recommendations=["Recapture the image using standard JPEG/PNG format."]
        )

    height, width = img.shape[:2]

    # Convert to grayscale for single-channel luminance metrics
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    sharpness = calculate_sharpness(gray)
    glare = calculate_glare_percentage(gray)

    issues: List[str] = []
    recommendations: List[str] = []

    # 1. Evaluate Resolution Adequacy
    total_pixels = width * height
    resolution_adequate = (
        width >= RESOLUTION_MIN_DIMENSION
        and height >= RESOLUTION_MIN_DIMENSION
        and total_pixels >= RESOLUTION_MIN_PIXELS
    )

    is_resolution_critical = (
        width < RESOLUTION_CRITICAL_DIMENSION
        or height < RESOLUTION_CRITICAL_DIMENSION
    )

    if is_resolution_critical:
        issues.append(f"Severely low resolution ({width}x{height}px). Essential text may be unreadable.")
        recommendations.append("Recapture image at higher camera resolution.")
    elif not resolution_adequate:
        issues.append(f"Suboptimal resolution ({width}x{height}px). Smaller mandatory declarations may be degraded.")
        recommendations.append("Take photo closer to the label or use higher resolution.")

    # 2. Evaluate Sharpness
    is_sharpness_critical = sharpness < SHARPNESS_DEGRADED_MIN
    is_sharpness_degraded = SHARPNESS_DEGRADED_MIN <= sharpness < SHARPNESS_ACCEPTABLE_MIN

    if is_sharpness_critical:
        issues.append(f"Severe blur detected (sharpness: {sharpness} < {SHARPNESS_DEGRADED_MIN}).")
        recommendations.append("Hold the camera steady and ensure focus before taking the picture.")
    elif is_sharpness_degraded:
        issues.append(f"Moderate blur detected (sharpness: {sharpness} < {SHARPNESS_ACCEPTABLE_MIN}). Fine text might be soft.")
        recommendations.append("Verify fine print manually or retake with sharper focus.")

    # 3. Evaluate Glare
    is_glare_critical = glare > GLARE_DEGRADED_MAX
    is_glare_degraded = GLARE_ACCEPTABLE_MAX < glare <= GLARE_DEGRADED_MAX

    if is_glare_critical:
        issues.append(f"Excessive surface glare/flash reflection detected ({glare}% clipped pixels).")
        recommendations.append("Turn off camera flash or change angle to eliminate reflections on glossy packaging.")
    elif is_glare_degraded:
        issues.append(f"Moderate glare detected ({glare}%). Portions of the label may be washed out.")
        recommendations.append("Adjust angle slightly to avoid direct light reflection.")

    # 4. Determine Overall Categorical Verdict
    if is_resolution_critical or is_sharpness_critical or is_glare_critical:
        verdict = QualityVerdict.UNREADABLE
    elif not resolution_adequate or is_sharpness_degraded or is_glare_degraded:
        verdict = QualityVerdict.WARNING_DEGRADED
    else:
        verdict = QualityVerdict.ACCEPTABLE

    return ImageQualityReport(
        sharpness_score=sharpness,
        glare_percentage=glare,
        width=width,
        height=height,
        resolution_adequate=resolution_adequate,
        quality_verdict=verdict,
        issues=issues,
        recommendations=recommendations
    )


def get_quality_metadata_path(image_file_path: Union[str, Path]) -> Path:
    """Returns the sidecar JSON path for an image's quality metadata."""
    return Path(str(image_file_path) + ".quality.json")


def save_quality_metadata(image_file_path: Union[str, Path], report: ImageQualityReport) -> None:
    """Saves image quality assessment as sidecar JSON."""
    try:
        sidecar_path = get_quality_metadata_path(image_file_path)
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)
    except Exception as e:
        logger.warning("Failed to save quality metadata to %s: %s", sidecar_path, e)


def load_quality_metadata(image_file_path: Union[str, Path]) -> Optional[ImageQualityReport]:
    """Loads image quality assessment from sidecar JSON if available."""
    sidecar_path = get_quality_metadata_path(image_file_path)
    if sidecar_path.exists():
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ImageQualityReport(**data)
        except Exception as e:
            logger.warning("Failed to parse quality metadata from %s: %s", sidecar_path, e)
    return None
