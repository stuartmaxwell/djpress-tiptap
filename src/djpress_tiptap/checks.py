"""Django system checks for DJ Press Tiptap configuration."""

from django.core.checks import Error as CheckError
from django.core.checks import Warning as CheckWarning
from django.core.checks import register
from djpress.conf import settings as djpress_settings

from djpress_tiptap import conf

LEGACY_HTML_STORAGE_WARNING = "djpress_tiptap.W001"
MARKDOWN_WITH_HTML_RENDERER_ERROR = "djpress_tiptap.E001"
LEGACY_HTML_RENDERER = "djpress_tiptap.renderers.html_renderer"


@register()
def check_legacy_html_storage(app_configs=None, **kwargs) -> list[CheckWarning]:  # noqa: ANN001, ANN003, ARG001
    """Warn when the deprecated HTML storage compatibility mode is enabled."""
    if conf.storage_format() != "html":
        return []

    return [
        CheckWarning(
            "DJPRESS_TIPTAP_STORAGE_FORMAT='html' enables deprecated HTML storage.",
            hint=(
                "Back up the database, run 'python manage.py djpress_tiptap_convert_to_markdown', "
                "then remove DJPRESS_TIPTAP_STORAGE_FORMAT (or set it to 'markdown') and restore DJ Press's "
                "Markdown renderer."
            ),
            id=LEGACY_HTML_STORAGE_WARNING,
        )
    ]


@register()
def check_markdown_renderer(app_configs=None, **kwargs) -> list[CheckError]:  # noqa: ANN001, ANN003, ARG001
    """Reject the legacy pass-through renderer when content is Markdown."""
    if conf.storage_format() != "markdown" or djpress_settings.CONTENT_RENDERER != LEGACY_HTML_RENDERER:
        return []

    return [
        CheckError(
            "DJ Press's legacy HTML renderer cannot render Markdown content.",
            hint=(
                f"Remove the CONTENT_RENDERER value '{LEGACY_HTML_RENDERER}' from DJPRESS_SETTINGS so DJ Press uses "
                "its default Markdown renderer, or configure another Markdown renderer."
            ),
            id=MARKDOWN_WITH_HTML_RENDERER_ERROR,
        )
    ]
