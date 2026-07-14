"""djpress-tiptap configuration.

Every setting is optional in the host project: these functions return the
project's DJPRESS_TIPTAP_* value when set, or the package default otherwise.

Functions rather than module-level constants so the settings are read lazily
(at request/render time): override_settings keeps working in tests, and the
module can be imported during app loading before settings are configured.
"""

from django.conf import settings
from django.shortcuts import resolve_url

# Pillow format name -> mime type. Keys validate what Pillow detected in the
# upload view; values are stored as Attachment.content_type and forwarded to
# the editor JS (file picker + drag-drop filter) via the widget's data-accept
# attribute. No SVG: it can carry scripts, making it an XSS vector.
DEFAULT_ALLOWED_IMAGE_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

# Mime types accepted by the video upload path, as detected by puremagic in
# the upload view, stored as Attachment.content_type, and forwarded to the
# editor JS via the widget's data-accept-video attribute. A set of mime types
# (not a format->mime dict like images) because puremagic reports mime types
# directly. Only web-playable formats: video/quicktime et al. would upload
# fine but not play in most browsers' <video> element. Set to an empty set to
# disable video uploads entirely.
DEFAULT_ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
}

DEFAULT_MAX_UPLOAD_SIZE_MB = 10

# Videos get their own, larger cap: even a short clip dwarfs any photo.
DEFAULT_MAX_VIDEO_UPLOAD_SIZE_MB = 100

# DJ Press Tiptap views to upload media
DJPRESS_TIPTAP_UPLOAD_URL = "djpress_tiptap:media_upload"
DJPRESS_TIPTAP_BROWSE_URL = "djpress_tiptap:media_browse"


def max_upload_size_mb() -> int:
    """Maximum attachment upload size in megabytes.

    Returns:
        The maximum upload size in megabytes, as configured via DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB.
    """
    return getattr(settings, "DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB", DEFAULT_MAX_UPLOAD_SIZE_MB)


def max_video_upload_size_mb() -> int:
    """Maximum video upload size in megabytes.

    Returns:
        The maximum video upload size in megabytes, as configured via
        DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB.
    """
    return getattr(settings, "DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB", DEFAULT_MAX_VIDEO_UPLOAD_SIZE_MB)


def allowed_image_types() -> dict[str, str]:
    """Mapping of accepted Pillow image formats to their mime types.

    Returns:
        The allowed image types, as configured via DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES.
    """
    return getattr(settings, "DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES", DEFAULT_ALLOWED_IMAGE_TYPES)


def allowed_video_types() -> set[str]:
    """Set of accepted video mime types.

    Returns:
        The allowed video mime types, as configured via DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES.
    """
    return getattr(settings, "DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES", DEFAULT_ALLOWED_VIDEO_TYPES)


def upload_url(override: str | None = None) -> str:
    """URL of the attachment upload endpoint.

    Priority: explicit widget argument, then DJPRESS_TIPTAP_UPLOAD_URL setting.
    Values may be a URL name or a path (LOGIN_URL semantics); the view just
    has to keep the JSON contract:
    POST multipart {file} -> 201 {url, alt?, ...} or 4xx {error}.

    When neither is set (or set to None/empty), returns "" and the widget
    disables uploads.

    Args:
        override: Optional URL override for the upload endpoint.

    Returns:
        The upload URL, as configured via DJPRESS_TIPTAP_UPLOAD_URL, or "" if unset.
    """
    url = override or getattr(settings, "DJPRESS_TIPTAP_UPLOAD_URL", DJPRESS_TIPTAP_UPLOAD_URL)
    return resolve_url(url) if url else ""


def browse_url(override: str | None = None) -> str:
    """URL of the media-library browse endpoint.

    Same priority and name-or-path semantics as upload_url, and likewise
    returns "" (feature disabled) when unset. The view returns an HTML
    fragment honouring the picker's data attributes: data-image-url /
    data-image-alt (insert), data-fetch (load another page), data-close
    (dismiss).

    Args:
        override: Optional URL override for the browse endpoint.

    Returns:
        The browse URL, as configured via DJPRESS_TIPTAP_BROWSE_URL, or "" if unset.
    """
    url = override or getattr(settings, "DJPRESS_TIPTAP_BROWSE_URL", DJPRESS_TIPTAP_BROWSE_URL)
    return resolve_url(url) if url else ""
