from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image

logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Union[str, Path]) -> str:
    """Computes the cryptographic SHA-256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_rotation_metadata_path(original_file_path: Union[str, Path]) -> Path:
    """Returns the sidecar JSON path for rotation metadata."""
    return Path(str(original_file_path) + ".meta.json")


def load_rotation_metadata(original_file_path: Union[str, Path]) -> Optional[dict]:
    """Loads rotation metadata from sidecar JSON if present."""
    meta_path = get_rotation_metadata_path(original_file_path)
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load rotation metadata from %s: %s", meta_path, e)
    return None


def save_rotation_metadata(original_file_path: Union[str, Path], meta: dict) -> None:
    """Saves rotation metadata to sidecar JSON."""
    meta_path = get_rotation_metadata_path(original_file_path)
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save rotation metadata to %s: %s", meta_path, e)


def get_active_image_file_path(original_file_path: Union[str, Path]) -> Tuple[Path, int]:
    """
    Returns (active_path, rotation_angle).
    If a rotated derivative exists, active_path is the derivative file.
    Otherwise active_path is the immutable original file.
    """
    orig_path = Path(original_file_path)
    meta = load_rotation_metadata(orig_path)
    if meta and meta.get("derivative_path"):
        deriv = Path(meta["derivative_path"])
        if deriv.exists():
            return deriv, int(meta.get("rotation_angle", 0))
    return orig_path, 0


def create_rotated_derivative(
    original_file_path: Union[str, Path],
    angle_clockwise: int
) -> Tuple[Path, dict]:
    """
    Creates a rotated derivative representation of the packaging image.

    CRITICAL EVIDENCE INTEGRITY INVARIANT:
    The original uploaded evidence file at original_file_path is NEVER overwritten,
    truncated, or modified. It remains strictly immutable.
    A derivative file is created at {original_file_path}.rot_{angle}.jpg, and a sidecar
    {original_file_path}.meta.json records the pristine original file's SHA-256 digest,
    rotation angle, derivative path, and timestamp.
    """
    orig = Path(original_file_path)
    if not orig.exists():
        raise FileNotFoundError(f"Original image file not found at {orig}")

    angle_norm = angle_clockwise % 360
    orig_sha256 = compute_file_sha256(orig)

    if angle_norm == 0:
        meta = {
            "original_sha256": orig_sha256,
            "original_path": str(orig),
            "rotation_angle": 0,
            "derivative_path": None,
            "is_derivative": False,
            "original_preserved": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        save_rotation_metadata(orig, meta)
        return orig, meta

    # Rotate with PIL (CW: 90 -> ROTATE_270 counter-clockwise transpose)
    with Image.open(orig) as im:
        if angle_norm == 90:
            rotated = im.transpose(Image.Transpose.ROTATE_270)
        elif angle_norm == 180:
            rotated = im.transpose(Image.Transpose.ROTATE_180)
        elif angle_norm == 270:
            rotated = im.transpose(Image.Transpose.ROTATE_90)
        else:
            rotated = im.rotate(-angle_norm, expand=True)

        derivative_path = Path(f"{orig}.rot_{angle_norm}.jpg")
        if rotated.mode in ("RGBA", "P"):
            rgb_img = Image.new("RGB", rotated.size, (255, 255, 255))
            if rotated.mode == "RGBA":
                rgb_img.paste(rotated, mask=rotated.split()[3])
            else:
                rgb_img.paste(rotated)
            rgb_img.save(derivative_path, "JPEG", quality=95)
        else:
            rotated.save(derivative_path, "JPEG", quality=95)

    meta = {
        "original_sha256": orig_sha256,
        "original_path": str(orig),
        "rotation_angle": angle_norm,
        "derivative_path": str(derivative_path),
        "is_derivative": True,
        "original_preserved": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_rotation_metadata(orig, meta)
    return derivative_path, meta
