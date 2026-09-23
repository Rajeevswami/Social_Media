"""Upload validation.

Size and content-type checks happen before a file is ever written to disk or
handed to Pillow, so a hostile upload cannot exhaust memory.
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def validate_image(file) -> None:
    """Reject oversized / non-image uploads."""
    max_bytes = settings.MAX_UPLOAD_BYTES
    size = getattr(file, "size", 0)
    if size > max_bytes:
        raise ValidationError(
            f"Image is too large ({size / (1024 * 1024):.1f} MB). "
            f"Maximum allowed is {max_bytes / (1024 * 1024):.0f} MB."
        )

    content_type = getattr(file, "content_type", "") or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            f"Unsupported image type '{content_type}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_IMAGE_TYPES))}."
        )
